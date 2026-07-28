from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from .config import HealthConfig
from .schemas.base import LLMResult

logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
            logger.debug("Created new httpx.AsyncClient, timeout=%.1f", self.config.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_schema: type | None = None,
    ) -> LLMResult:
        model = model or self.config.model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        logger.debug("LLM request: model=%s, msgs=%d, temp=%.2f, max_tokens=%d", model, len(messages), temperature, max_tokens)

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.config.mlx_url.rstrip('/')}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info("LLM response: model=%s, len=%d", model, len(content))

            if response_schema:
                return self._parse_structured(content, response_schema, model)
            return LLMResult(content=content, raw=content, model=model)

        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP error: %s %s", e.response.status_code, e.response.text[:200])
            return LLMResult(content="", error=f"HTTP {e.response.status_code}", model=model)
        except KeyError as e:
            logger.error("LLM response missing key: %s", e)
            return LLMResult(content="", error=f"response_missing_key: {e}", model=model)
        except Exception as e:
            logger.error("LLM error: %s", type(e).__name__, exc_info=True)
            return LLMResult(content="", error=str(e), model=model)

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        model = model or self.config.model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        logger.debug("LLM stream request: model=%s, msgs=%d", model, len(messages))

        client = await self._get_client()
        try:
            async with client.stream(
                "POST",
                f"{self.config.mlx_url.rstrip('/')}/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        logger.warning("Stream chunk parse error: %s", data[:100])
                        continue
        except Exception as e:
            logger.error("LLM stream error: %s", type(e).__name__, exc_info=True)
            yield f"[stream error: {e}]"

    def _parse_structured(self, content: str, schema: type, model: str) -> LLMResult:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            validated = schema.model_validate(data)
            logger.info("Schema validation passed: %s", schema.__name__)
            return LLMResult(content=content, parsed=validated, model=model)
        except json.JSONDecodeError as e:
            logger.warning("JSON decode failed: %s, raw: %s", e, content[:200])
            return LLMResult(
                content=content,
                error=f"schema_validation_failed: json_decode_error",
                raw=content,
                model=model,
            )
        except Exception as e:
            logger.warning("Schema validation failed: %s, raw: %s", e, content[:200])
            return LLMResult(
                content=content,
                error=f"schema_validation_failed: {type(e).__name__}",
                raw=content,
                model=model,
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("Closed httpx.AsyncClient")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
