from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query, Request

from ... import audit as audit_mod

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/verify")
async def verify(request: Request) -> dict:
    config = request.app.state.config
    log_path = getattr(config, "audit_log_path", None)
    verified, tampered = audit_mod.verify_log_file(log_path)
    return {
        "log_path": str(log_path) if log_path else str(audit_mod._log_path()),
        "verified": verified,
        "tampered": tampered,
        "intact": tampered == 0,
    }


@router.get("/recent")
async def recent(request: Request, limit: int = Query(default=50, ge=1, le=500)) -> dict:
    config = request.app.state.config
    log_path = getattr(config, "audit_log_path", None) or audit_mod._log_path()
    events: list[dict] = []
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            body = line.rsplit("\t", 1)[0]
            try:
                events.append(json.loads(body))
            except json.JSONDecodeError:
                logger.warning("audit recent: skipping malformed line")
    return {"events": events, "count": len(events), "log_path": str(log_path)}
