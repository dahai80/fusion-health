from __future__ import annotations

from pydantic import BaseModel


class ClinicalSummary(BaseModel):
    chief_complaint: str = ""
    history: str = ""
    examination_findings: str = ""
    diagnosis: str = ""
    treatment_plan: str = ""
    confidence_notes: str = ""


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
