from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...tcm.assistant import TCMAssistant
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class TCMAnalyzeRequest(BaseModel):
    symptoms: str = Field(..., min_length=1, max_length=5000)


class TCMSyndromeRequest(BaseModel):
    symptoms: str = Field(..., min_length=1, max_length=5000)


class TCMFormulaRequest(BaseModel):
    syndrome_id: str = Field(..., min_length=1, max_length=50)


class TCMContraindicationRequest(BaseModel):
    herbs: list[str] = Field(..., min_length=1)


@router.post("/analyze")
async def analyze(request: Request, body: TCMAnalyzeRequest) -> dict[str, Any]:
    config = request.app.state.config
    assistant = TCMAssistant(config)
    return await assistant.analyze(body.symptoms)


@router.post("/analyze/stream")
async def analyze_stream(request: Request, body: TCMAnalyzeRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "从中医角度分析以下症状，包括辨证、治法和方药建议：\n\n"
            f"{body.symptoms[:4000]}"
        )}],
    )
    return sse_response(tokens, request, gateway)


@router.post("/syndrome")
async def identify_syndrome(request: Request, body: TCMSyndromeRequest) -> dict[str, Any]:
    config = request.app.state.config
    assistant = TCMAssistant(config)
    results = assistant.identify_syndrome(body.symptoms)
    return {"syndromes": results}


@router.post("/formula")
async def recommend_formula(request: Request, body: TCMFormulaRequest) -> dict[str, Any]:
    config = request.app.state.config
    assistant = TCMAssistant(config)
    formulas = assistant.recommend_formula(body.syndrome_id)
    return {"formulas": formulas}


@router.post("/contraindications")
async def check_contraindications(request: Request, body: TCMContraindicationRequest) -> dict[str, Any]:
    config = request.app.state.config
    assistant = TCMAssistant(config)
    violations = assistant.check_contraindications(body.herbs)
    return {"violations": violations}
