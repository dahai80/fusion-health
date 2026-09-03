from __future__ import annotations

import logging
import re
from typing import Any

from ..config import HealthConfig
from ..schemas.base import VerificationStatus

logger = logging.getLogger(__name__)

CPT_CODE_RE = re.compile(r"^\d{4,5}[A-Z0-9]?$")


class CPTValidator:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config

    def validate(self, code: str) -> dict[str, Any]:
        cleaned = (code or "").strip().upper()
        if not cleaned:
            return {"valid": False, "description": "", "status": VerificationStatus.invalid}
        if not CPT_CODE_RE.match(cleaned):
            logger.warning("CPT code format invalid: %s", code)
            return {"valid": False, "description": "", "status": VerificationStatus.invalid}
        return {
            "valid": True,
            "description": "",
            "status": VerificationStatus.ai_suggested,
            "note": "format-valid, no CPT database loaded for full verification",
        }
