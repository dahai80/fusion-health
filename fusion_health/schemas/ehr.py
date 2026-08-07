from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClinicalSummary(BaseModel):
    chief_complaint: Any = ""
    history: Any = ""
    examination_findings: Any = ""
    diagnosis: Any = ""
    treatment_plan: Any = ""
    confidence_notes: Any = ""


class DischargeSummary(BaseModel):
    diagnosis: str = ""
    procedures: str = ""
    hospital_course: str = ""
    discharge_medications: str = ""
    follow_up_plan: str = ""


class VitalsResult(BaseModel):
    bp: str = ""
    hr: str = ""
    temp: str = ""
    rr: str = ""
    spo2: str = ""
