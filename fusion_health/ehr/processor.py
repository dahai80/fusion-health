from __future__ import annotations

import logging
from typing import Any

from ..config import HealthConfig
from ..llm_gateway import LLMGateway
from ..schemas.ehr import ClinicalSummary, SOURCE_AI_GENERATED, VitalsResult

logger = logging.getLogger(__name__)


class EHRProcessor:
    def __init__(self, config: HealthConfig | None = None, mlx_url: str | None = None):
        if config is None:
            config = HealthConfig.from_env()
        if mlx_url is not None:
            config.mlx_url = mlx_url
        self.config = config
        self._gateway = LLMGateway(config)

    async def generate_summary(self, clinical_notes: str) -> dict[str, Any]:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                "Extract a structured clinical summary from these notes. "
                "Include: chief_complaint, history, examination_findings, diagnosis, treatment_plan. "
                "Return as JSON.\n\n" + clinical_notes[:4000]
            )}],
            max_tokens=2048,
            response_schema=ClinicalSummary,
        )
        if result.parsed:
            logger.warning("EHR summary is AI-generated and UNVERIFIED — not a clinical diagnosis")
            return {**result.parsed.model_dump(), "source": SOURCE_AI_GENERATED}
        if result.error:
            logger.error("generate_summary error: %s", result.error)
            return {"error": result.error, "raw": result.raw}
        return {"summary": result.content, "source": SOURCE_AI_GENERATED}

    async def generate_discharge_summary(self, admission_notes: str, progress_notes: str,
                                           discharge_meds: str) -> str:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Generate a discharge summary from:\n\n"
                f"Admission: {admission_notes[:2000]}\n\n"
                f"Progress: {progress_notes[:2000]}\n\n"
                f"Discharge meds: {discharge_meds[:1000]}\n\n"
                f"Include: diagnosis, procedures, hospital course, discharge medications, follow-up plan."
            )}],
            max_tokens=4096,
        )
        if result.error:
            logger.error("generate_discharge_summary error: %s", result.error)
            return f"Error: {result.error}"
        return result.content

    async def extract_vitals(self, text: str) -> dict[str, Any]:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Extract all vital signs from this clinical text. "
                f"Return as JSON: {{'bp': '', 'hr': '', 'temp': '', 'rr': '', 'spo2': ''}}\n\n{text[:2000]}"
            )}],
            max_tokens=512,
            temperature=0.0,
            response_schema=VitalsResult,
        )
        if result.parsed:
            return {**result.parsed.model_dump(), "source": SOURCE_AI_GENERATED}
        if result.error:
            logger.error("extract_vitals error: %s", result.error)
            return {"error": result.error, "raw": result.raw}
        return {"vitals": result.content, "source": SOURCE_AI_GENERATED}
