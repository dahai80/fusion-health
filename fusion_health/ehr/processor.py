"""EHR processor — automates medical record handling, coding, and documentation."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class EHRProcessor:
    """Processes electronic health records — summaries, coding, documentation."""

    def __init__(self, mlx_url: str = "http://localhost:11434/v1"):
        self.mlx_url = mlx_url.rstrip("/")

    async def generate_summary(self, clinical_notes: str) -> dict[str, Any]:
        """Generate a structured clinical summary from raw notes."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        "Extract a structured clinical summary from these notes. "
                        "Include: chief complaint, history, examination findings, diagnosis, treatment plan. "
                        "Return as JSON.\n\n" + clinical_notes[:4000]
                    )}],
                    "max_tokens": 2048, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.startswith("{") else {"summary": content}
        except Exception as e:
            return {"error": str(e)}

    async def generate_discharge_summary(self, admission_notes: str, progress_notes: str,
                                           discharge_meds: str) -> str:
        """Generate a complete discharge summary."""
        prompt = (
            f"Generate a discharge summary from:\n\n"
            f"Admission: {admission_notes[:2000]}\n\n"
            f"Progress: {progress_notes[:2000]}\n\n"
            f"Discharge meds: {discharge_meds[:1000]}\n\n"
            f"Include: diagnosis, procedures, hospital course, discharge medications, follow-up plan."
        )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096, "temperature": 0.1,
                })
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {e}"

    async def extract_vitals(self, text: str) -> dict[str, Any]:
        """Extract vital signs and key metrics from clinical text."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Extract all vital signs from this clinical text. "
                        f"Return as JSON: {{'bp': '', 'hr': '', 'temp': '', 'rr': '', 'spo2': ''}}\n\n{text[:2000]}"
                    )}],
                    "max_tokens": 512, "temperature": 0.0,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.startswith("{") else {"vitals": content}
        except Exception as e:
            return {"error": str(e)}