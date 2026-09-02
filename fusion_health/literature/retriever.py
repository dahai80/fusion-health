from __future__ import annotations

import logging
from typing import Any

from ..config import HealthConfig
from ..llm_gateway import LLMGateway
from ..schemas.literature import LiteratureSearchResult, SOURCE_AI_UNVERIFIED
from .pubmed_client import PubMedClient
from .semantic_scholar import SemanticScholarClient

logger = logging.getLogger(__name__)


class LiteratureRetriever:
    def __init__(self, config: HealthConfig | None = None, mlx_url: str | None = None):
        if config is None:
            config = HealthConfig.from_env()
        if mlx_url is not None:
            config.mlx_url = mlx_url
        self.config = config
        self._gateway = LLMGateway(config)
        self._pubmed = PubMedClient(timeout=config.timeout)
        self._s2 = SemanticScholarClient(timeout=config.timeout)

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        real_results = await self._fetch_real_sources(query, max_results)
        if real_results:
            return real_results
        logger.info("No real literature sources available, falling back to LLM")
        return await self._search_via_llm(query, max_results)

    async def _fetch_real_sources(self, query: str, max_results: int) -> list[dict[str, Any]]:
        results = []
        if self.config.pubmed_enabled:
            try:
                pubmed = await self._pubmed.search(query, max_results=max_results)
                results.extend(pubmed)
            except Exception as e:
                logger.warning("PubMed fetch failed: %s", e)
        if len(results) < max_results and self.config.semantic_scholar_enabled:
            try:
                s2 = await self._s2.search(query, max_results=max_results - len(results))
                seen_dois = {r.get("doi", "") for r in results if r.get("doi")}
                for item in s2:
                    if item.get("doi") not in seen_dois:
                        results.append(item)
            except Exception as e:
                logger.warning("Semantic Scholar fetch failed: %s", e)
        return results[:max_results]

    async def _search_via_llm(self, query: str, max_results: int) -> list[dict[str, Any]]:
        logger.warning(
            "Falling back to LLM-generated literature for query=%r — results are "
            "AI-generated and UNVERIFIED, not real citations", query,
        )
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Search clinical literature for: {query}\n"
                f"Return {max_results} relevant studies as JSON: "
                f"{{'results': [{{'title': str, 'authors': str, 'journal': str, 'year': int, 'summary': str}}]}}"
            )}],
            max_tokens=2048,
            response_schema=LiteratureSearchResult,
        )
        if result.parsed:
            items = []
            for item in result.parsed.results:
                dumped = item.model_dump()
                dumped["source"] = SOURCE_AI_UNVERIFIED
                items.append(dumped)
            return items
        if result.error:
            logger.error("search error: %s", result.error)
        return []

    async def summarize_evidence(self, topic: str, literature: list[dict]) -> str:
        lit_text = "\n".join(f"- {item.get('title', '?')}: {item.get('summary', '')[:200]}" for item in literature[:10])
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Summarize clinical evidence for: {topic}\n\nLiterature:\n{lit_text}\n\n"
                f"Provide evidence-based recommendations with citations."
            )}],
            max_tokens=2048,
        )
        if result.error:
            logger.error("summarize_evidence error: %s", result.error)
            return f"Error: {result.error}"
        return result.content
