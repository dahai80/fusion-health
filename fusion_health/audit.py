from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _hash_phi(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def log_access(
    owner_id: str,
    method: str,
    path: str,
    action: str,
    status: str,
    phi_input: str = "",
    request_id: str = "",
) -> None:
    if os.getenv("FUSION_HEALTH_AUDIT_DISABLED", "0") == "1":
        return
    log_path = Path(os.getenv("FUSION_HEALTH_AUDIT_LOG", "")) or (
        Path.home() / ".fusion-health" / "audit.log"
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "owner_id": owner_id,
            "method": method,
            "path": path,
            "action": action,
            "status": status,
            "phi_input_hash": _hash_phi(phi_input),
            "phi_input_len": len(phi_input),
        }
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with _lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        logger.error("audit log write failed: %s", e)
