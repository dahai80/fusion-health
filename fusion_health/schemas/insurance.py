from __future__ import annotations

from typing import Any

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


class ClaimAuditResult(BaseModel):
    issues: list[Any] = []
    error: str = ""
