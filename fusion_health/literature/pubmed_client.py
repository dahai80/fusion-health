from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
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
            esearch_resp = await client.get(f"{PUBMED_BASE}/esearch.fcgi", params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
            })
            esearch_resp.raise_for_status()
            id_list = esearch_resp.json().get("esearchresult", {}).get("idlist", [])

            if not id_list:
                logger.info("PubMed search: query=%s, no results", query)
                return []

            esummary_resp = await client.get(f"{PUBMED_BASE}/esummary.fcgi", params={
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            })
            esummary_resp.raise_for_status()
            summaries = esummary_resp.json().get("result", {})

            results = []
            for pmid in id_list:
                info = summaries.get(pmid, {})
                results.append({
                    "title": info.get("title", ""),
                    "authors": ", ".join(a.get("name", "") for a in info.get("authors", [])),
                    "journal": info.get("fulljournalname", info.get("source", "")),
                    "year": int(info.get("sortpubdate", "0000")[:4]) if info.get("sortpubdate") else 0,
                    "doi": info.get("elocationid", ""),
                    "pmid": pmid,
                    "source": "pubmed",
                    "summary": info.get("sorttitle", ""),
                })
            logger.info("PubMed search: query=%s, found=%d", query, len(results))
            return results
        except Exception as e:
            logger.error("PubMed search failed: %s", e)
            return []
