from __future__ import annotations

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    config = getattr(request.app.state, "config", None)
    return {
        "status": "ok",
        "service": "fusion-health",
        "version": "0.2.0",
        "model": config.model if config else "unknown",
    }
