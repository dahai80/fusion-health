from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_seq = 0


def _audit_key() -> bytes:
    raw = os.getenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "")
    if not raw:
        raw = os.getenv("FUSION_HEALTH_API_KEY", "") or "fusion-health-audit-default"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _hash_phi(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _hmac(line: str) -> str:
    return hmac.new(_audit_key(), line.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _log_path() -> Path:
    p = os.getenv("FUSION_HEALTH_AUDIT_LOG", "")
    return Path(p) if p else (Path.home() / ".fusion-health" / "audit.log")


def log_access(
    owner_id: str,
    method: str,
    path: str,
    action: str,
    status: str,
    phi_input: str = "",
    request_id: str = "",
) -> None:
    global _seq
    if os.getenv("FUSION_HEALTH_AUDIT_DISABLED", "0") == "1":
        return
    try:
        log_path = _log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            _seq += 1
            event = {
                "seq": _seq,
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
            body = json.dumps(event, ensure_ascii=False, sort_keys=True)
            sig = _hmac(body)
            line = f"{body}\t{sig}\n"
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                with os.fdopen(fd, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                os.close(fd)
                raise
    except Exception as e:
        logger.error("audit log write failed: %s", e)


def verify_log_line(line: str) -> bool:
    parts = line.rstrip("\n").rsplit("\t", 1)
    if len(parts) != 2:
        return False
    body, sig = parts
    return hmac.compare_digest(sig, _hmac(body))


def verify_log_file(path: Path | None = None) -> tuple[int, int]:
    """Verify every line's HMAC. Returns (verified_count, tampered_count)."""
    log_path = path or _log_path()
    if not log_path.exists():
        logger.warning("audit log not found for verify: %s", log_path)
        return 0, 0
    verified = 0
    tampered = 0
    last_seq = 0
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            if not verify_log_line(line):
                tampered += 1
                continue
            try:
                body = line.rstrip("\n").rsplit("\t", 1)[0]
                event = json.loads(body)
                seq = int(event.get("seq", 0))
                if seq != last_seq + 1 and last_seq > 0:
                    logger.warning("audit seq gap: expected %d got %d", last_seq + 1, seq)
                    tampered += 1
                    continue
                last_seq = seq
            except Exception:
                tampered += 1
                continue
            verified += 1
    if tampered:
        logger.error("audit verification FAILED: %d tampered/gap lines in %s", tampered, log_path)
    else:
        logger.info("audit verification OK: %d lines intact in %s", verified, log_path)
    return verified, tampered


def rotate_log(max_bytes: int = 10 * 1024 * 1024, keep: int = 5) -> Path | None:
    """Rotate audit log when it exceeds max_bytes. Keeps `keep` archives.

    Archives named audit.log.1, .2, ... Rotated atomically (rename). Returns
    the rotated archive path or None if no rotation occurred.
    """
    log_path = _log_path()
    if not log_path.exists() or log_path.stat().st_size < max_bytes:
        return None
    with _lock:
        if log_path.stat().st_size < max_bytes:
            return None
        for i in range(keep, 0, -1):
            src = log_path.parent / f"audit.log.{i}"
            dst = log_path.parent / f"audit.log.{i + 1}" if i < keep else None
            if src.exists():
                if dst:
                    src.rename(dst)
                else:
                    src.unlink()
        archive = log_path.parent / "audit.log.1"
        log_path.rename(archive)
        log_path.touch()
        os.chmod(log_path, 0o600)
        logger.info("audit log rotated: %s -> %s", log_path, archive)
        return archive

