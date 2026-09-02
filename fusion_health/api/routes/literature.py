from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...literature.retriever import LiteratureRetriever
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)


class EvidenceRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    literature: list[dict] = Field(default_factory=list)


@router.post("/search")
async def search_literature(request: Request, body: SearchRequest) -> list[dict[str, Any]]:
    config = request.app.state.config
    retriever = LiteratureRetriever(config)
    return await retriever.search(body.query, body.max_results)


@router.post("/evidence")
async def summarize_evidence(request: Request, body: EvidenceRequest) -> dict[str, Any]:
    config = request.app.state.config
    retriever = LiteratureRetriever(config)
    summary = await retriever.summarize_evidence(body.topic, body.literature)
    return {"evidence_summary": summary}


@router.post("/evidence/stream")
async def summarize_evidence_stream(request: Request, body: EvidenceRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            f"Summarize the evidence on this topic: {body.topic}\n\n"
            f"Literature: {body.literature[:10]}"
        )}],
    )
    return sse_response(tokens, request, gateway)
