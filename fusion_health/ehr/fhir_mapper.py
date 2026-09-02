from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..schemas.fhir import (
    FHIRBundle, FHIRCodeableConcept, FHIRCondition, FHIRObservation,
    FHIRProcedure, FHIRMedicationRequest,
)

logger = logging.getLogger(__name__)


class FHIRMapper:
    def map_vitals(self, vitals: dict[str, Any]) -> FHIRBundle:
        entries = []
        now = datetime.now(timezone.utc).isoformat()
        mappings = {
            "bp": {"code": "85354-9", "display": "Blood pressure panel", "system": "http://loinc.org"},
            "hr": {"code": "8867-4", "display": "Heart rate", "system": "http://loinc.org"},
            "temp": {"code": "8310-5", "display": "Body temperature", "system": "http://loinc.org"},
            "rr": {"code": "9279-1", "display": "Respiratory rate", "system": "http://loinc.org"},
            "spo2": {"code": "2708-6", "display": "Oxygen saturation", "system": "http://loinc.org"},
        }
        for key, value in vitals.items():
            if not value:
                continue
            meta = mappings.get(key, {"code": "", "display": key, "system": ""})
            obs = FHIRObservation(
                id=str(uuid.uuid4()),
                status="final",
                code=FHIRCodeableConcept(
                    text=meta["display"],
                    code=meta["code"],
                    system=meta["system"],
                ),
                valueString=str(value),
                effectiveDateTime=now,
            )
            entries.append({"resource": json.loads(obs.model_dump_json())})
        return FHIRBundle(entry=entries)

    def map_diagnosis(self, diagnoses: list[dict[str, Any]]) -> FHIRBundle:
        entries = []
        for diag in diagnoses:
            cond = FHIRCondition(
                id=str(uuid.uuid4()),
                status="final",
                code=FHIRCodeableConcept(
                    text=diag.get("description", ""),
                    code=diag.get("code", ""),
                    system="http://hl7.org/fhir/sid/icd-10",
                ),
                clinicalStatus=FHIRCodeableConcept(text="active"),
            )
            entries.append({"resource": json.loads(cond.model_dump_json())})
        return FHIRBundle(entry=entries)

    def map_procedure(self, procedures: list[dict[str, Any]]) -> FHIRBundle:
        entries = []
        for proc in procedures:
            p = FHIRProcedure(
                id=str(uuid.uuid4()),
                status="completed",
                code=FHIRCodeableConcept(
                    text=proc.get("description", ""),
                    code=proc.get("code", ""),
                    system="http://hl7.org/fhir/sid/icd-9-cm",
                ),
            )
            entries.append({"resource": json.loads(p.model_dump_json())})
        return FHIRBundle(entry=entries)

    def map_medication(self, medications: list[dict[str, Any]]) -> FHIRBundle:
        entries = []
        for med in medications:
            mr = FHIRMedicationRequest(
                id=str(uuid.uuid4()),
                status="active",
                medicationCodeableConcept=FHIRCodeableConcept(
                    text=med.get("name", med.get("description", "")),
                    code=med.get("code", ""),
                ),
                authoredOn=datetime.now(timezone.utc).isoformat(),
            )
            entries.append({"resource": json.loads(mr.model_dump_json())})
        return FHIRBundle(entry=entries)

    def map_clinical_summary(self, summary: dict[str, Any]) -> FHIRBundle:
        all_entries = []
        if summary.get("vitals"):
            bundle = self.map_vitals(summary["vitals"])
            all_entries.extend(bundle.entry)
        if summary.get("diagnoses") or summary.get("diagnosis"):
            diags = summary.get("diagnoses") or [{"code": "", "description": summary.get("diagnosis", "")}]
            bundle = self.map_diagnosis(diags)
            all_entries.extend(bundle.entry)
        if summary.get("procedures"):
            bundle = self.map_procedure(summary["procedures"])
            all_entries.extend(bundle.entry)
        if summary.get("medications"):
            bundle = self.map_medication(summary["medications"])
            all_entries.extend(bundle.entry)
        return FHIRBundle(entry=all_entries)

    def to_json(self, bundle: FHIRBundle) -> str:
        return bundle.model_dump_json(indent=2)
