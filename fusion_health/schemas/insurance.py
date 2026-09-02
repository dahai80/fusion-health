from __future__ import annotations

from pydantic import BaseModel

from .base import VerificationStatus


class ICDCodeItem(BaseModel):
    code: str = ""
    description: str = ""
    status: VerificationStatus = VerificationStatus.ai_suggested
    source: str = "ai"


class ICDCodeResult(BaseModel):
    codes: list[ICDCodeItem] = []
    error: str = ""


class CPTCodeItem(BaseModel):
    code: str = ""
    description: str = ""
    status: VerificationStatus = VerificationStatus.ai_suggested
    source: str = "ai"


class CPTCodeResult(BaseModel):
    codes: list[CPTCodeItem] = []
    error: str = ""


class ClaimIssueItem(BaseModel):
    severity: str = "warning"
    category: str = ""
    detail: str = ""


class ClaimData(BaseModel):
    patient_id: str = ""
    diagnosis_codes: list[str] = []
    procedure_codes: list[str] = []
    billed_amount: str = ""
    provider: str = ""
    service_date: str = ""
    notes: str = ""


class ClaimAuditResult(BaseModel):
    issues: list[ClaimIssueItem] = []
    error: str = ""


class ProcedureCodeItem(BaseModel):
    code: str = ""
    description: str = ""
    status: VerificationStatus = VerificationStatus.ai_suggested


class ProcedureCodeResult(BaseModel):
    codes: list[ProcedureCodeItem] = []
    error: str = ""


class DRGItem(BaseModel):
    drg_code: str = ""
    drg_name: str = ""
    mdc: str = ""
    category: str = ""


class DRGResult(BaseModel):
    results: list[DRGItem] = []
    error: str = ""
