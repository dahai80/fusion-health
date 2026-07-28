from __future__ import annotations

from pydantic import BaseModel, Field


class FHIRCodeableConcept(BaseModel):
    text: str = ""
    code: str = ""
    system: str = ""


class FHIRCoding(BaseModel):
    system: str = ""
    code: str = ""
    display: str = ""


class FHIRResource(BaseModel):
    resourceType: str = ""
    id: str = ""
    status: str = ""


class FHIRPatient(FHIRResource):
    resourceType: str = "Patient"
    name: list[dict] = Field(default_factory=list)
    gender: str = ""
    birthDate: str = ""


class FHIRObservation(FHIRResource):
    resourceType: str = "Observation"
    code: FHIRCodeableConcept = Field(default_factory=FHIRCodeableConcept)
    valueString: str = ""
    valueQuantity: dict = Field(default_factory=dict)
    effectiveDateTime: str = ""


class FHIRCondition(FHIRResource):
    resourceType: str = "Condition"
    code: FHIRCodeableConcept = Field(default_factory=FHIRCodeableConcept)
    clinicalStatus: FHIRCodeableConcept = Field(default_factory=FHIRCodeableConcept)


class FHIRProcedure(FHIRResource):
    resourceType: str = "Procedure"
    code: FHIRCodeableConcept = Field(default_factory=FHIRCodeableConcept)


class FHIRMedicationRequest(FHIRResource):
    resourceType: str = "MedicationRequest"
    medicationCodeableConcept: FHIRCodeableConcept = Field(default_factory=FHIRCodeableConcept)
    authoredOn: str = ""


class FHIRBundle(BaseModel):
    resourceType: str = "Bundle"
    type: str = "collection"
    entry: list[dict] = Field(default_factory=list)
