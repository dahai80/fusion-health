from __future__ import annotations

from pydantic import BaseModel

SOURCE_PUBMED = "pubmed"
SOURCE_SEMANTIC_SCHOLAR = "semantic_scholar"
SOURCE_AI_UNVERIFIED = "ai_generated_unverified"


class LiteratureItem(BaseModel):
    title: str = ""
    authors: str = ""
    journal: str = ""
    year: int = 0
    doi: str = ""
    pmid: str = ""
    source: str = SOURCE_PUBMED
    summary: str = ""


class LiteratureSearchResult(BaseModel):
    results: list[LiteratureItem] = []
    total_found: int = 0
    offline: bool = False
    error: str = ""
