"""Literature retriever — clinical literature search and evidence-based medicine support."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LiteratureRetriever:
    """Clinical literature search and evidence-based medicine retrieval."""

    def __init__(self, mlx_url: str = "http://localhost:11434/v1"):
        self.mlx_url = mlx_url.rstrip("/")

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search clinical literature by query."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Search clinical literature for: {query}\n"
                        f"Return {max_results} relevant studies as JSON array: "
                        f"[{{'title': str, 'authors': str, 'journal': str, 'year': int, 'summary': str}}]"
                    )}],
                    "max_tokens": 2048, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.strip().startswith("[") else []
        except Exception:
            return []

    async def summarize_evidence(self, topic: str, literature: list[dict]) -> str:
        """Summarize clinical evidence for a topic."""
        lit_text = "\n".join(f"- {l.get('title', '?')}: {l.get('summary', '')[:200]}" for l in literature[:10])
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Summarize clinical evidence for: {topic}\n\nLiterature:\n{lit_text}\n\n"
                        f"Provide evidence-based recommendations with citations."
                    )}],
                    "max_tokens": 2048, "temperature": 0.1,
                })
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {e}"


class ComplianceChecker:
    """Medical compliance checking — documentation audit, regulation compliance."""

    def __init__(self, mlx_url: str = "http://localhost:11434/v1"):
        self.mlx_url = mlx_url.rstrip("/")

    async def audit_documentation(self, clinical_note: str) -> dict[str, Any]:
        """Audit clinical documentation for completeness and compliance."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Audit this clinical note for: 1) completeness, 2) missing elements, "
                        f"3) coding accuracy, 4) regulatory compliance. "
                        f"Return as JSON with 'issues' array.\n\n{clinical_note[:4000]}"
                    )}],
                    "max_tokens": 2048, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.startswith("{") else {"issues": [content]}
        except Exception as e:
            return {"error": str(e)}

    async def check_regulatory_compliance(self, document_type: str, content: str) -> dict[str, Any]:
        """Check document compliance with healthcare regulations."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.mlx_url}/chat/completions", json={
                    "model": "qwen3.5-9b",
                    "messages": [{"role": "user", "content": (
                        f"Check this {document_type} for regulatory compliance. "
                        f"Identify any compliance gaps or risks. "
                        f"Return as JSON with 'compliant' bool and 'issues' array.\n\n{content[:3000]}"
                    )}],
                    "max_tokens": 2048, "temperature": 0.1,
                })
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                import json
                return json.loads(content) if content.startswith("{") else {"compliant": False, "issues": [content]}
        except Exception as e:
            return {"error": str(e)}