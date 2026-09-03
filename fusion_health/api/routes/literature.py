from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...audit import log_access
from ...literature.retriever import LiteratureRetriever
from ..gateway_provider import get_gateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class EvidenceRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    literature: list[dict] = Field(default_factory=list)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _owner(request: Request) -> str:
    return getattr(request.state, "owner_id", "anonymous")


@router.post("/search")
async def search_literature(request: Request, body: SearchRequest) -> list[dict[str, Any]]:
    config = request.app.state.config
    retriever = LiteratureRetriever(config)
    try:
        results = await retriever.search(body.query, body.max_results)
    finally:
        await retriever.aclose()
    log_access(_owner(request), "POST", "/api/v1/literature/search", "lit_search", "ok", body.query, _req_id(request))
    return results


@router.post("/evidence")
async def summarize_evidence(request: Request, body: EvidenceRequest) -> dict[str, Any]:
    config = request.app.state.config
    retriever = LiteratureRetriever(config)
    try:
        summary = await retriever.summarize_evidence(body.topic, body.literature)
    finally:
        await retriever.aclose()
    log_access(_owner(request), "POST", "/api/v1/literature/evidence", "lit_evidence", "ok", body.topic, _req_id(request))
    return {"evidence_summary": summary}


@router.post("/evidence/stream")
async def summarize_evidence_stream(request: Request, body: EvidenceRequest):
    config = request.app.state.config
    gateway = get_gateway(config)
    lit_text = "\n".join(
        f"- {item.get('title', '?')}: {item.get('summary', '')[:200]}"
        for item in body.literature[:10]
    )
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            f"Summarize clinical evidence for: {body.topic}\n\nLiterature:\n{lit_text}\n\n"
            f"Provide evidence-based recommendations with citations."
        )}],
    )
    return sse_response(tokens, request, gateway)


async def close_all_clients():
    logger.info("Literature route shutdown — clients are per-request, nothing to close")
