from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...insurance.coder import InsuranceCoder
from ...insurance.cn_coding import CNMedicalCoder
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()


class ICD10Request(BaseModel):
    diagnosis_text: str = Field(..., min_length=1, max_length=5000)


class CPTRequest(BaseModel):
    procedure_text: str = Field(..., min_length=1, max_length=5000)


class ClaimAuditRequest(BaseModel):
    claim_data: dict


class DRGRequest(BaseModel):
    diagnosis_or_procedure: str = Field(..., min_length=1, max_length=2000)


class CatalogRequest(BaseModel):
    icd_codes: list[str] = Field(..., min_length=1)


class ProcedureCodeRequest(BaseModel):
    procedure_text: str = Field(..., min_length=1, max_length=5000)


@router.post("/icd10")
async def suggest_icd10(request: Request, body: ICD10Request) -> list[dict[str, Any]]:
    config = request.app.state.config
    coder = InsuranceCoder(config)
    return await coder.suggest_icd_codes(body.diagnosis_text)


@router.post("/icd10/stream")
async def suggest_icd10_stream(request: Request, body: ICD10Request):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "Suggest ICD-10 codes for this diagnosis text. "
            "List each code with description.\n\n"
            f"{body.diagnosis_text[:4000]}"
        )}],
    )
    return sse_response(tokens, request, gateway)


@router.post("/cpt")
async def suggest_cpt(request: Request, body: CPTRequest) -> list[dict[str, Any]]:
    config = request.app.state.config
    coder = InsuranceCoder(config)
    return await coder.suggest_cpt_codes(body.procedure_text)


@router.post("/cpt/stream")
async def suggest_cpt_stream(request: Request, body: CPTRequest):
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(
        messages=[{"role": "user", "content": (
            "Suggest CPT codes for this procedure text. "
            "List each code with description.\n\n"
            f"{body.procedure_text[:4000]}"
        )}],
    )
    return sse_response(tokens, request, gateway)


@router.post("/claim-audit")
async def audit_claim(request: Request, body: ClaimAuditRequest) -> dict[str, Any]:
    config = request.app.state.config
    coder = InsuranceCoder(config)
    return await coder.audit_claim(body.claim_data)


@router.post("/drg")
async def suggest_drg(request: Request, body: DRGRequest) -> dict[str, Any]:
    config = request.app.state.config
    cn_coder = CNMedicalCoder(config)
    return await cn_coder.suggest_drg(body.diagnosis_or_procedure)


@router.post("/catalog")
async def match_catalog(request: Request, body: CatalogRequest) -> list[dict[str, Any]]:
    config = request.app.state.config
    cn_coder = CNMedicalCoder(config)
    return cn_coder.match_insurance_catalog(body.icd_codes)


@router.post("/procedure-codes")
async def suggest_procedure_codes(request: Request, body: ProcedureCodeRequest) -> list[dict[str, Any]]:
    config = request.app.state.config
    cn_coder = CNMedicalCoder(config)
    return await cn_coder.suggest_procedure_codes(body.procedure_text)
