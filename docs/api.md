# Fusion-Health API Reference

---

## `fusion_health.ehr.processor`

```python
from fusion_health.ehr.processor import EHRProcessor
```

| Method | Returns | Description |
|--------|---------|-------------|
| `generate_summary(clinical_notes)` | `dict` | Structured clinical summary |
| `generate_discharge_summary(admission, progress, meds)` | `str` | Discharge summary |
| `extract_vitals(text)` | `dict` | Vital signs extraction |

---

## `fusion_health.insurance.coder`

```python
from fusion_health.insurance.coder import InsuranceCoder
```

| Method | Returns | Description |
|--------|---------|-------------|
| `suggest_icd_codes(diagnosis_text)` | `list[dict]` | ICD-10 diagnosis codes |
| `suggest_cpt_codes(procedure_text)` | `list[dict]` | CPT procedure codes |
| `audit_claim(claim_data)` | `dict` | Insurance claim audit |

---

## `fusion_health.literature.retriever`

```python
from fusion_health.literature.retriever import LiteratureRetriever, ComplianceChecker
```

### LiteratureRetriever
| Method | Returns | Description |
|--------|---------|-------------|
| `search(query, max_results)` | `list[dict]` | Clinical literature search |
| `summarize_evidence(topic, literature)` | `str` | Evidence-based summary |

### ComplianceChecker
| Method | Returns | Description |
|--------|---------|-------------|
| `audit_documentation(clinical_note)` | `dict` | Documentation compliance audit |
| `check_regulatory_compliance(document_type, content)` | `dict` | Regulatory compliance check |