from __future__ import annotations

import logging
from importlib.metadata import version as pkg_version

import httpx
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    config = getattr(request.app.state, "config", None)
    try:
        ver = pkg_version("fusion-health")
    except Exception:
        ver = "0.0.0"

    backend_ok = False
    backend_error = ""
    if config is not None:
        models_url = f"{config.mlx_url.rstrip('/')}/models"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers: dict[str, str] = {}
                if config.mlx_route:
                    headers["X-Fusion-Route"] = config.mlx_route
                if config.mlx_api_key:
                    headers["Authorization"] = f"Bearer {config.mlx_api_key}"
                resp = await client.get(models_url, headers=headers)
                if resp.status_code == 200:
                    backend_ok = True
                else:
                    backend_error = f"backend_http_{resp.status_code}"
        except Exception as e:
            backend_error = f"backend_unreachable: {type(e).__name__}"
            logger.warning("Health check backend probe failed: %s", backend_error)

    status = "ok" if backend_ok else "degraded"
    base = {
        "status": status,
        "service": "fusion-health",
        "version": ver,
        "model": config.model if config else "unknown",
        "backend": {"ok": backend_ok, "error": backend_error},
    }
    if backend_ok:
        return base
    return JSONResponse(status_code=503, content=base)
