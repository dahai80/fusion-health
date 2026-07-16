<div align="center">

# Fusion-Health

**Local AI Healthcare Assistant — Powered by fusion-mlx**

Process medical records, generate clinical summaries, suggest ICD-10/CPT codes, search clinical literature, and check compliance — entirely local, no data leaves your device.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-18-success.svg)](tests/)

[Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Architecture](#architecture) · [Documentation](docs/)

</div>

---

## Why Fusion-Health?

| Feature | Fusion-Health | Claude Health |
|---------|--------------|--------------|
| **Local offline** | ✅ 100% local | ❌ Cloud-only |
| **Data privacy** | ✅ PHI never leaves device | ❌ Data uploaded to cloud |
| **China compliance** | ✅ Full compliance | ❌ Violates PIPL |
| **Zero API cost** | ✅ | ❌ Enterprise subscription |
| **EHR processing** | ✅ Summaries, discharge, vitals | ✅ |
| **ICD-10/CPT coding** | ✅ AI-assisted coding | ✅ |
| **Literature search** | ✅ Evidence-based retrieval | ✅ |
| **Compliance auditing** | ✅ Documentation audit | ✅ |
| **Chinese medical support** | ✅ Native Chinese | ❌ Limited |

**One sentence:** Fusion-Health is the local-first, privacy-compliant alternative to Claude Health — powered by fusion-mlx on Apple Silicon.

---

## Quick Start

### Prerequisites

- macOS with Apple Silicon (M1–M5), Python 3.12+
- [fusion-mlx](https://github.com/dahai80/fusion-mlx) running on `localhost:11434`

### Install

```bash
git clone https://github.com/dahai80/fusion-health.git
cd fusion-health
pip install -e ".[test]"
```

### Process Medical Records

```bash
# Generate clinical summary
fusion-health ehr summary --input=clinical_notes.txt --output=summary.json

# Generate discharge summary
fusion-health ehr discharge --input=admission_notes.txt --output=discharge.md

# Extract vital signs
fusion-health ehr vitals --input=progress_notes.txt
```

### Medical Coding

```bash
# Suggest ICD-10 codes
fusion-health code icd10 --input="Patient with hypertension and diabetes"

# Suggest CPT codes
fusion-health code cpt --input="Office visit, level 3"

# Audit insurance claim
fusion-health code audit --input=claim_data.txt
```

### Literature Search

```bash
fusion-health literature "diabetes type 2 treatment guidelines" --max-results=10
```

### Compliance Checking

```bash
fusion-health compliance audit --input=clinical_note.txt
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `ehr summary --input [--output]` | Generate structured clinical summary |
| `ehr discharge --input [--output]` | Generate discharge summary |
| `ehr vitals --input` | Extract vital signs |
| `code icd10 --input` | Suggest ICD-10 diagnosis codes |
| `code cpt --input` | Suggest CPT procedure codes |
| `code audit --input` | Audit insurance claim |
| `literature <query> [--max-results]` | Search clinical literature |
| `compliance audit --input` | Audit clinical documentation |
| `compliance regulatory --input --type` | Check regulatory compliance |
| `version` | Show version |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fusion-Health CLI                             │
│  ehr · code · literature · compliance                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     Core Engine                                  │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ EHRProcessor   │  │ InsuranceCoder │  │ LiteratureRetriever│ │
│  │ · summaries    │  │ · ICD-10 codes │  │ · clinical search │  │
│  │ · discharge    │  │ · CPT codes    │  │ · evidence summary│  │
│  │ · vitals       │  │ · claim audit  │  │                  │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ComplianceChecker                                         │  │
│  │ · documentation audit · regulatory compliance check       │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP API
┌───────────────────────────▼─────────────────────────────────────┐
│                    fusion-mlx (/v1/chat/completions)              │
│                    Apple Silicon MLX Runtime                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Comparison with Claude Health

| Capability | Claude Health | Fusion-Health |
|------------|-------------|--------------|
| EHR clinical summaries | ✅ | ✅ |
| Discharge summaries | ✅ | ✅ |
| Vital signs extraction | ✅ | ✅ |
| ICD-10 coding | ✅ | ✅ |
| CPT coding | ✅ | ✅ |
| Claim auditing | ✅ | ✅ |
| Literature search | ✅ | ✅ |
| Evidence-based summaries | ✅ | ✅ |
| Documentation audit | ✅ | ✅ |
| Regulatory compliance | ✅ | ✅ |
| **Local offline** | ❌ Cloud-only | ✅ **100% local** |
| **Data privacy** | ❌ PHI uploaded | ✅ **Data never leaves** |
| **China compliance** | ❌ Violates PIPL | ✅ **Full compliance** |
| **Zero API cost** | ❌ Enterprise | ✅ **Free** |
| **Chinese medical support** | ❌ Limited | ✅ **Native** |

---

## License

MIT

## Acknowledgments

- [fusion-mlx](https://github.com/dahai80/fusion-mlx) — Apple Silicon model serving
- [Claude Health](https://www.anthropic.com/healthcare) — Reference architecture