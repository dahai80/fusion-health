from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def production_readiness_check(config) -> list[dict]:
    failures: list[dict] = []

    data_source = "sample"
    marker = Path(getattr(config, "data_dir", ".")) / ".data_source"
    try:
        if marker.exists():
            data_source = marker.read_text(encoding="utf-8").strip() or "sample"
    except OSError:
        pass
    if data_source != "full":
        failures.append({
            "check": "data_source",
            "detail": f"data_source={data_source}, must be 'full' (run scripts/ingest_data.py)",
        })

    if not os.getenv("FUSION_HEALTH_API_KEY", "").strip():
        failures.append({
            "check": "api_key",
            "detail": "FUSION_HEALTH_API_KEY unset — remote access rejected (localhost-only)",
        })

    if not os.getenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "").strip():
        failures.append({
            "check": "audit_hmac_key",
            "detail": "FUSION_HEALTH_AUDIT_HMAC_KEY unset — audit signatures use fallback key",
        })

    if not os.getenv("FUSION_HEALTH_PHI_KEY", "").strip():
        failures.append({
            "check": "phi_encryption",
            "detail": "FUSION_HEALTH_PHI_KEY unset — conversation PHI stored in plaintext",
        })

    cors = os.getenv("FUSION_HEALTH_CORS_ORIGINS", "").strip()
    if cors in ("", "*"):
        failures.append({
            "check": "cors",
            "detail": f"FUSION_HEALTH_CORS_ORIGINS={'unset' if not cors else '*'} — set explicit origins",
        })

    return failures


def assert_enterprise_ready(config) -> bool:
    enterprise = os.getenv("FUSION_HEALTH_ENTERPRISE", "0") == "1"
    if not enterprise:
        return True
    failures = production_readiness_check(config)
    if not failures:
        logger.info("Enterprise production readiness: PASS (all checks green)")
        return True
    hard = os.getenv("FUSION_HEALTH_ENTERPRISE_HARD", "0") == "1"
    for f in failures:
        logger.error("Enterprise readiness FAIL — %s: %s", f["check"], f["detail"])
    if hard:
        raise RuntimeError(
            f"Enterprise production readiness checks failed ({len(failures)}): "
            + ", ".join(f["check"] for f in failures)
        )
    logger.warning("Enterprise mode active but %d readiness checks failed (soft mode — continuing)", len(failures))
    return False
