"""Insurance coder — ICD-10/CPT coding and insurance claim processing."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class InsuranceCoder:
    """Medical coding and insurance claim assistance."""

    def __init__(self, mlx_url: str = "http://localhost:11434/v1"):
        self.mlx_url = mlx_url.rstrip("/")

    async def suggest_icd_codes(self, diagnosis_text: str) -> list[dict[str, Any]]:
        """Suggest ICD-10 diagnosis codes from clinical text."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Suggest ICD-10 diagnosis codes for: {diagnosis_text[:2000]}\n"
                        f"Return as JSON array: [{{'code': 'I10', 'description': '...', 'confidence': 0.95}}]"
                    )}],
                    "max_tokens": 1024, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.strip().startswith("[") else []
        except Exception:
            return []

    async def suggest_cpt_codes(self, procedure_text: str) -> list[dict[str, Any]]:
        """Suggest CPT procedure codes."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Suggest CPT procedure codes for: {procedure_text[:2000]}\n"
                        f"Return as JSON array: [{{'code': '99213', 'description': '...', 'confidence': 0.9}}]"
                    )}],
                    "max_tokens": 1024, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.strip().startswith("[") else []
        except Exception:
            return []

    async def audit_claim(self, claim_data: dict) -> dict[str, Any]:
        """Audit an insurance claim for completeness and compliance."""
        text = str(claim_data)[:3000]
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Audit this insurance claim. Identify missing items, coding errors, "
                        f"and compliance issues. Return as JSON with 'issues' array.\n\n{text}"
                    )}],
                    "max_tokens": 1024, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.startswith("{") else {"issues": [content]}
        except Exception as e:
            return {"error": str(e)}