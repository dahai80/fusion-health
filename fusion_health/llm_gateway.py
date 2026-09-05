from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from fusion_core.http_client import get_async_client, with_retry

from .config import HealthConfig
from .schemas.base import LLMResult

logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._client: httpx.AsyncClient | None = None
        self._resolved_model: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.config.mlx_route:
            headers["X-Fusion-Route"] = self.config.mlx_route
        if self.config.mlx_api_key:
            headers["Authorization"] = f"Bearer {self.config.mlx_api_key}"
        return headers

    async def _resolve_model(self, requested: str) -> str:
        if self._resolved_model is not None:
            return self._resolved_model
        candidate = requested
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.config.mlx_url.rstrip('/')}/models",
                headers=self._auth_headers(),
            )
            if resp.status_code != 200:
                logger.warning(
                    "Model resolve skipped: /models returned %s (check mlx_url/mlx_api_key)",
                    resp.status_code,
                )
                self._resolved_model = candidate
                return candidate
            ids = [m.get("id", "") for m in resp.json().get("data", [])]
            if candidate in ids:
                self._resolved_model = candidate
                return candidate
            lower = candidate.lower()
            matches = [i for i in ids if lower in i.lower()]
            if len(matches) == 1:
                logger.info("Model alias resolved: %s -> %s", candidate, matches[0])
                self._resolved_model = matches[0]
                return matches[0]
            if len(matches) > 1:
                exact = [i for i in matches if i.lower().endswith("--" + lower)]
                if len(exact) == 1:
                    logger.info("Model alias resolved: %s -> %s", candidate, exact[0])
                    self._resolved_model = exact[0]
                    return exact[0]
                logger.warning(
                    "Model %r ambiguous among %d loaded models %s; using as-is (may 404)",
                    candidate, len(matches), matches[:5],
                )
                self._resolved_model = candidate
                return candidate
            logger.warning(
                "Model %r not found in %d loaded models %s; using as-is (will 404 unless loaded later)",
                candidate, len(ids), ids[:5],
            )
            self._resolved_model = candidate
            return candidate
        except Exception as e:
            logger.warning("Model resolve failed (%s: %s); using %s as-is", type(e).__name__, e, candidate)
            self._resolved_model = candidate
            return candidate

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = get_async_client(
                self.config.mlx_url,
                timeout=self.config.timeout,
            )
            logger.debug("Pooled httpx.AsyncClient via fusion_core, base=%s", self.config.mlx_url)
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

        model = await self._resolve_model(model)

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        logger.debug("LLM request: model=%s, msgs=%d, temp=%.2f, max_tokens=%d", model, len(messages), temperature, max_tokens)

        client = await self._get_client()
        headers = self._auth_headers()
        try:
            resp = await with_retry(
                lambda: client.post(
                    f"{self.config.mlx_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                ),
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info("LLM response: model=%s, len=%d", model, len(content))

            if not content or not content.strip():
                logger.warning("LLM returned empty content, model=%s", model)
                return LLMResult(content="", error="empty_content", model=model)

            if response_schema:
                return self._parse_structured(content, response_schema, model)
            return LLMResult(content=content, raw=content, model=model)

        except httpx.HTTPStatusError as e:
            sc = e.response.status_code
            logger.error("LLM HTTP error: %s", sc)
            hint = ""
            if sc == 401:
                hint = (
                    " (401: auth failed — gateway needs FUSION_MLX_API_KEY env; "
                    "direct-mlx needs FUSION_HEALTH_MLX_ROUTE=chat + key from ~/.fusion-mlx/settings.json)"
                )
            elif sc == 404:
                hint = " (404: model not loaded on backend — check /v1/models)"
            return LLMResult(content="", error=f"HTTP {sc}{hint}", model=model)
        except KeyError as e:
            logger.error("LLM response missing key: %s", e)
            return LLMResult(content="", error=f"response_missing_key: {e}", model=model)
        except Exception as e:
            logger.error("LLM error: %s: %s", type(e).__name__, e, exc_info=logger.isEnabledFor(logging.DEBUG))
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

        model = await self._resolve_model(model)

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
                headers=self._auth_headers(),
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
            logger.error("LLM stream error: %s, len(yielded)=%d", type(e).__name__, 0)
            raise

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
            logger.warning("JSON decode failed: %s, content_len=%d", e, len(content))
            return LLMResult(
                content=content,
                error="schema_validation_failed: json_decode_error",
                raw=content,
                model=model,
            )
        except Exception as e:
            logger.warning("Schema validation failed: %s, content_len=%d", type(e).__name__, len(content))
            return LLMResult(
                content=content,
                error=f"schema_validation_failed: {type(e).__name__}",
                raw=content,
                model=model,
            )

    async def close(self):
        if self._client is not None:
            logger.debug("Releasing reference to pooled httpx.AsyncClient (pool-managed, not closed)")
        self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
