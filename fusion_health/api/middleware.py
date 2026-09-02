from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    norm = path
    while "//" in norm:
        norm = norm.replace("//", "/")
    try:
        from urllib.parse import unquote
        norm = unquote(norm)
    except Exception:
        pass
    return norm


def _owner_id(api_key: str, client_host: str) -> str:
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return f"local:{client_host}"


class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, owner_id: str) -> bool:
        if self.rpm <= 0:
            return True
        now = time.monotonic()
        window = 60.0
        hits = self._hits[owner_id]
        cutoff = now - window
        while hits and hits[0] < cutoff:
            hits.pop(0)
        if len(hits) >= self.rpm:
            return False
        hits.append(now)
        return True


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        rpm = int(os.getenv("FUSION_HEALTH_RATE_LIMIT_RPM", "0") or "0")
        self.limiter = RateLimiter(rpm)

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        path = _normalize_path(request.url.path)

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
        if not api_key:
            client_host = request.client.host if request.client else ""
            if client_host in ("127.0.0.1", "::1", "localhost"):
                owner = _owner_id("", client_host)
                request.state.owner_id = owner
                return await self._gate(request, call_next, owner, path)
            logger.warning(
                "API key not set; rejecting non-localhost access: %s %s",
                request.method, path,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "API key required: set FUSION_HEALTH_API_KEY for remote access"},
            )

        key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key, api_key):
            logger.warning("Unauthorized API access: %s %s", request.method, path)
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        owner = _owner_id(api_key, request.client.host if request.client else "")
        request.state.owner_id = owner
        return await self._gate(request, call_next, owner, path)

    async def _gate(self, request, call_next, owner, path):
        if not self.limiter.allow(owner):
            logger.warning("Rate limit exceeded: owner=%s %s %s", owner, request.method, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after": 60},
            )
        return await call_next(request)
