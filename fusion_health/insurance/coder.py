from __future__ import annotations

import logging
from typing import Any

from ..config import HealthConfig
from ..llm_gateway import LLMGateway
from ..schemas.base import VerificationStatus
from ..schemas.insurance import ICDCodeResult, CPTCodeResult, ClaimAuditResult
from .icd_validator import ICDValidator

logger = logging.getLogger(__name__)


class InsuranceCoder:
    def __init__(self, config: HealthConfig | None = None, mlx_url: str | None = None):
        if config is None:
            config = HealthConfig.from_env()
        if mlx_url is not None:
            config.mlx_url = mlx_url
        self.config = config
        self._gateway = LLMGateway(config)
        self._validator = ICDValidator(config)

    async def suggest_icd_codes(self, diagnosis_text: str) -> list[dict[str, Any]]:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Suggest ICD-10 diagnosis codes for: {diagnosis_text[:2000]}\n"
                f"Return as JSON: {{'codes': [{{'code': 'I10', 'description': '...', 'status': 'ai_suggested'}}]}}"
            )}],
            max_tokens=1024,
            response_schema=ICDCodeResult,
        )
        if result.parsed:
            codes = [item.model_dump() for item in result.parsed.codes]
            return self._annotate_with_validator(codes)
        if result.error:
            logger.error("suggest_icd_codes error: %s", result.error)
        return []

    def _annotate_with_validator(self, codes: list[dict]) -> list[dict]:
        for item in codes:
            code = item.get("code", "")
            validation = self._validator.validate(code)
            if validation["valid"]:
                item["status"] = VerificationStatus.verified
                item["description"] = validation["description"] or item.get("description", "")
            else:
                item["status"] = VerificationStatus.ai_suggested
        return codes

    async def suggest_cpt_codes(self, procedure_text: str) -> list[dict[str, Any]]:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Suggest CPT procedure codes for: {procedure_text[:2000]}\n"
                f"Return as JSON: {{'codes': [{{'code': '99213', 'description': '...', 'status': 'ai_suggested'}}]}}"
            )}],
            max_tokens=1024,
            response_schema=CPTCodeResult,
        )
        if result.parsed:
            return [item.model_dump() for item in result.parsed.codes]
        if result.error:
            logger.error("suggest_cpt_codes error: %s", result.error)
        return []

    async def audit_claim(self, claim_data: dict) -> dict[str, Any]:
        import json
        try:
            text = json.dumps(claim_data, ensure_ascii=False)[:3000]
        except Exception:
            text = str(claim_data)[:3000]

        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Audit this insurance claim. Identify missing items, coding errors, "
                f"and compliance issues. Return as JSON with 'issues' array.\n\n{text}"
            )}],
            max_tokens=1024,
            response_schema=ClaimAuditResult,
        )
        if result.parsed:
            return result.parsed.model_dump()
        if result.error:
            logger.error("audit_claim error: %s", result.error)
            return {"error": result.error, "raw": result.raw}
        return {"issues": [result.content]}
