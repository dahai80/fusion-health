from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
        if not api_key:
            return await call_next(request)

        exempt_paths = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}
        if request.url.path in exempt_paths:
            return await call_next(request)

        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        query_key = request.query_params.get("api_key", "")
        if key != api_key and query_key != api_key:
            logger.warning("Unauthorized API access: %s %s", request.method, request.url.path)
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)
