from __future__ import annotations

import logging
from importlib.metadata import version as pkg_version
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _version() -> str:
    try:
        return pkg_version("fusion-health")
    except Exception:
        return "0.0.0"


def _data_file_status(config) -> dict[str, str]:
    status: dict[str, str] = {}
    if config is None:
        return status
    data_dir = Path(getattr(config, "data_dir", "."))
    candidates = {
        "icd10_cn": data_dir / "icd10_cn" / "icd10_cn.tsv",
        "drg": data_dir / "drg" / "drg_cn.tsv",
        "catalog": data_dir / "insurance_catalog.tsv",
        "icd9cm3": data_dir / "icd9cm3_cn" / "icd9cm3_cn.tsv",
    }
    for name, path in candidates.items():
        status[name] = "loaded" if path.exists() else "missing"
    return status


def _session_count(request: Request) -> int:
    try:
        from .chat import _sessions
        return len(_sessions)
    except Exception:
        return 0


@router.get("/health")
async def health_check(request: Request):
    config = getattr(request.app.state, "config", None)
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
        "version": _version(),
        "model": config.model if config else "unknown",
        "backend": {"ok": backend_ok, "error": backend_error},
        "data_files": _data_file_status(config),
        "sessions": _session_count(request),
    }
    if backend_ok:
        return base
    return JSONResponse(status_code=503, content=base)


@router.get("/health/ready")
async def readiness(request: Request):
    config = getattr(request.app.state, "config", None)
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
            logger.warning("Readiness backend probe failed: %s", backend_error)

    status = "ready" if backend_ok else "degraded"
    from ...enterprise import production_readiness_check
    failures = production_readiness_check(config) if config else []
    body = {
        "status": status,
        "service": "fusion-health",
        "version": _version(),
        "backend_ok": backend_ok,
        "data_files": _data_file_status(config),
        "sessions": _session_count(request),
        "enterprise_ready": len(failures) == 0,
        "enterprise_failures": failures,
    }
    if not backend_ok:
        body["error"] = backend_error
    if backend_ok and not failures:
        return body
    return JSONResponse(status_code=503, content=body)
