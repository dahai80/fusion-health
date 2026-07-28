from __future__ import annotations

from pydantic import BaseModel


class LiteratureItem(BaseModel):
    title: str = ""
    authors: str = ""
    journal: str = ""
    year: int = 0
    doi: str = ""
    pmid: str = ""
    source: str = "pubmed"
    summary: str = ""


class LiteratureSearchResult(BaseModel):
    results: list[LiteratureItem] = []
    total_found: int = 0
    offline: bool = False
    error: str = ""
