from __future__ import annotations

import logging
from importlib.metadata import version as pkg_version

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    config = getattr(request.app.state, "config", None)
    try:
        ver = pkg_version("fusion-health")
    except Exception:
        ver = "0.0.0"
    return {
        "status": "ok",
        "service": "fusion-health",
        "version": ver,
        "model": config.model if config else "unknown",
    }
