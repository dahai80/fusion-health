from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...ehr.processor import EHRProcessor
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class SummaryRequest(BaseModel):
    clinical_notes: str = Field(..., min_length=1, max_length=10000)


class DischargeRequest(BaseModel):
    admission_notes: str = Field(..., min_length=1, max_length=5000)
    progress_notes: str = Field(..., min_length=1, max_length=5000)
    discharge_meds: str = Field(..., min_length=1, max_length=3000)


class VitalsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


@router.post("/summary")
async def generate_summary(request: Request, body: SummaryRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    return await processor.generate_summary(body.clinical_notes)


@router.post("/summary/stream")
async def generate_summary_stream(request: Request, body: SummaryRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "Generate a clinical summary for these notes. "
            "Include chief complaint, history, assessment, and plan.\n\n"
            f"{body.clinical_notes[:8000]}"
        )}],
    )
    return sse_response(tokens, request, gateway)


@router.post("/discharge")
async def generate_discharge(request: Request, body: DischargeRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    summary = await processor.generate_discharge_summary(
        body.admission_notes, body.progress_notes, body.discharge_meds,
    )
    return {"discharge_summary": summary}


@router.post("/discharge/stream")
async def generate_discharge_stream(request: Request, body: DischargeRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "Generate a discharge summary.\n"
            f"Admission: {body.admission_notes[:3000]}\n"
            f"Progress: {body.progress_notes[:3000]}\n"
            f"Meds: {body.discharge_meds[:2000]}"
        )}],
    )
    return sse_response(tokens, request, gateway)


@router.post("/vitals")
async def extract_vitals(request: Request, body: VitalsRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    return await processor.extract_vitals(body.text)
