from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

S2_BASE = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        try:
            client = await self._get_client()
            resp = await client.get(f"{S2_BASE}/paper/search", params={
                "query": query,
                "limit": max_results,
                "fields": "title,authors,year,externalIds,abstract,journal",
            })
            resp.raise_for_status()
            data = resp.json().get("data", [])

            results = []
            for paper in data:
                ext_ids = paper.get("externalIds", {})
                doi = ext_ids.get("DOI", "")
                pmid = ext_ids.get("PubMed", "")
                authors = ", ".join(a.get("name", "") for a in paper.get("authors", []))
                journal_info = paper.get("journal") or {}
                results.append({
                    "title": paper.get("title", ""),
                    "authors": authors,
                    "journal": journal_info.get("name", ""),
                    "year": paper.get("year") or 0,
                    "doi": doi,
                    "pmid": str(pmid) if pmid else "",
                    "source": "semantic_scholar",
                    "summary": paper.get("abstract", "") or "",
                })
            logger.info("Semantic Scholar search: query=%s, found=%d", query, len(results))
            return results
        except Exception as e:
            logger.error("Semantic Scholar search failed: %s", e)
            return []
