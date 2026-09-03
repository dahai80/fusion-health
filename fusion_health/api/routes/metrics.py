from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics")
async def metrics() -> dict:
    from ..middleware import APIKeyMiddleware
    mw = APIKeyMiddleware._instance
    if mw is None:
        logger.warning("Metrics requested but middleware not initialized")
        return {"available": False}
    return {"available": True, **mw.metrics_snapshot()}
