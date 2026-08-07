from __future__ import annotations

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        exempt_paths = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}
        if request.url.path in exempt_paths:
            return await call_next(request)

        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
        if not api_key:
            client_host = request.client.host if request.client else ""
            if client_host in ("127.0.0.1", "::1", "localhost"):
                return await call_next(request)
            logger.warning(
                "API key not set; rejecting non-localhost access: %s %s",
                request.method, request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "API key required: set FUSION_HEALTH_API_KEY for remote access"},
            )

        key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key, api_key):
            logger.warning("Unauthorized API access: %s %s", request.method, request.url.path)
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)
