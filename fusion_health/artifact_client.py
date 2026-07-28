from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import HealthConfig

logger = logging.getLogger(__name__)


class ArtifactClient:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._base_url = self.config.artifacts_url

    async def create(
        self,
        session_id: str,
        name: str,
        content: str,
        artifact_type: str = "text",
        kind: str = "document",
        metadata: dict | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.create",
            "params": {
                "session_id": session_id,
                "name": name,
                "type": artifact_type,
                "content": content,
                "kind": kind,
                "metadata": metadata or {},
            },
            "id": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._base_url, json=payload)
                resp.raise_for_status()
                result = resp.json().get("result")
                logger.info("Artifact created: name=%s, session=%s", name, session_id)
                return result
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return None

    async def list_artifacts(self, session_id: str) -> list[dict]:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.list",
            "params": {"session_id": session_id},
            "id": 2,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._base_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("result", [])
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return []

    async def get_artifact(self, session_id: str, artifact_id: str) -> dict[str, Any] | None:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.get",
            "params": {"session_id": session_id, "artifact_id": artifact_id},
            "id": 3,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._base_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("result")
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return None

    async def export_artifact(self, session_id: str, artifact_id: str, format: str = "markdown") -> str | None:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.export",
            "params": {"session_id": session_id, "artifact_id": artifact_id, "format": format},
            "id": 4,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._base_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("result", {}).get("content")
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return None
