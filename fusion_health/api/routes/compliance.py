from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...compliance.checker import ComplianceChecker
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class AuditRequest(BaseModel):
    clinical_note: str = Field(..., min_length=1, max_length=10000)


class RegulatoryRequest(BaseModel):
    document_type: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)


@router.post("/audit")
async def audit_documentation(request: Request, body: AuditRequest) -> dict[str, Any]:
    config = request.app.state.config
    checker = ComplianceChecker(config)
    return await checker.audit_documentation(body.clinical_note)


@router.post("/audit/stream")
async def audit_documentation_stream(request: Request, body: AuditRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "Audit this clinical note for completeness, missing elements, "
            "coding accuracy, and regulatory compliance.\n\n"
            f"{body.clinical_note[:8000]}"
        )}],
    )
    return sse_response(tokens)


@router.post("/regulatory")
async def check_regulatory(request: Request, body: RegulatoryRequest) -> dict[str, Any]:
    config = request.app.state.config
    checker = ComplianceChecker(config)
    return await checker.check_regulatory_compliance(body.document_type, body.content)


@router.post("/regulatory/stream")
async def check_regulatory_stream(request: Request, body: RegulatoryRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            f"Check this {body.document_type} for regulatory compliance. "
            "Identify any compliance gaps or risks.\n\n"
            f"{body.content[:8000]}"
        )}],
    )
    return sse_response(tokens)
