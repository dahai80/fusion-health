from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...audit import log_access
from ...ehr.processor import EHRProcessor, SYSTEM_PROMPT
from ...ehr.fhir_mapper import FHIRMapper
from ..gateway_provider import get_gateway
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


class FHIRRequest(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    vitals: dict[str, Any] = Field(default_factory=dict)
    diagnoses: list[dict[str, Any]] = Field(default_factory=list)
    procedures: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)


def _owner(request: Request) -> str:
    return getattr(request.state, "owner_id", "anonymous")


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _audit(request: Request, action: str, status: str, phi_input: str = ""):
    log_access(_owner(request), "POST", f"/api/v1/ehr/{action}", action, status, phi_input, _req_id(request))


@router.post("/summary")
async def generate_summary(request: Request, body: SummaryRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    result = await processor.generate_summary(body.clinical_notes)
    _audit(request, "summary", "error" if isinstance(result, dict) and result.get("error") else "ok", body.clinical_notes)
    return result


@router.post("/summary/stream")
async def generate_summary_stream(request: Request, body: SummaryRequest):
    config = request.app.state.config
    gateway = get_gateway(config)
    tokens = gateway.chat_stream(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Generate a clinical summary for these notes. "
                "Include chief complaint, history, assessment, and plan.\n\n"
                f"{body.clinical_notes[:8000]}"
            )},
        ],
    )
    _audit(request, "summary/stream", "ok", body.clinical_notes)
    return sse_response(tokens, request, gateway)


@router.post("/discharge")
async def generate_discharge(request: Request, body: DischargeRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    summary = await processor.generate_discharge_summary(
        body.admission_notes, body.progress_notes, body.discharge_meds,
    )
    _audit(request, "discharge", "ok", body.admission_notes)
    return {"discharge_summary": summary}


@router.post("/discharge/stream")
async def generate_discharge_stream(request: Request, body: DischargeRequest):
    config = request.app.state.config
    gateway = get_gateway(config)
    tokens = gateway.chat_stream(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Generate a discharge summary.\n"
                f"Admission: {body.admission_notes[:3000]}\n"
                f"Progress: {body.progress_notes[:3000]}\n"
                f"Meds: {body.discharge_meds[:2000]}"
            )},
        ],
    )
    _audit(request, "discharge/stream", "ok", body.admission_notes)
    return sse_response(tokens, request, gateway)


@router.post("/vitals")
async def extract_vitals(request: Request, body: VitalsRequest) -> dict[str, Any]:
    config = request.app.state.config
    processor = EHRProcessor(config)
    result = await processor.extract_vitals(body.text)
    _audit(request, "vitals", "error" if isinstance(result, dict) and result.get("error") else "ok", body.text)
    return result


@router.post("/fhir")
async def map_fhir(request: Request, body: FHIRRequest) -> dict[str, Any]:
    mapper = FHIRMapper()
    data = body.model_dump()
    if data.get("summary"):
        bundle = mapper.map_clinical_summary(data["summary"])
    else:
        from ...schemas.fhir import FHIRBundle
        entries = []
        if data.get("vitals"):
            entries.extend(mapper.map_vitals(data["vitals"]).entry)
        if data.get("diagnoses"):
            entries.extend(mapper.map_diagnosis(data["diagnoses"]).entry)
        if data.get("procedures"):
            entries.extend(mapper.map_procedure(data["procedures"]).entry)
        if data.get("medications"):
            entries.extend(mapper.map_medication(data["medications"]).entry)
        bundle = FHIRBundle(entry=entries)
    _audit(request, "fhir", "ok")
    return {"fhir": bundle.model_dump(), "resourceType": "Bundle"}
