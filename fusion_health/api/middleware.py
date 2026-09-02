from __future__ import annotations

import hashlib
import hmac
import logging
import os

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
    return norm


def _owner_id(api_key: str, client_host: str) -> str:
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return f"local:{client_host}"


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = _normalize_path(request.url.path)
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
        if not api_key:
            client_host = request.client.host if request.client else ""
            if client_host in ("127.0.0.1", "::1", "localhost"):
                request.state.owner_id = _owner_id("", client_host)
                return await call_next(request)
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

        request.state.owner_id = _owner_id(api_key, request.client.host if request.client else "")
        return await call_next(request)
