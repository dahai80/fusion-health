<div align="center">

# Fusion-Health

**Local AI Healthcare Assistant — Powered by fusion-mlx**

Process medical records, generate clinical summaries, suggest ICD-10/CPT codes, search clinical literature, and check compliance — entirely local, no data leaves your device.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-128-success.svg)](tests/)

[Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Architecture](#architecture) · [Documentation](docs/)

English | **[中文](README_CN.md)**

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
- [fusion-mlx](https://github.com/dahai80/fusion-mlx) running on `localhost:11434` (default model `Qwen3.5-9B-4bit`)

### Install

```bash
git clone https://github.com/dahai80/fusion-health.git
cd fusion-health
pip install -e ".[test]"

# For API server support
pip install -e ".[api]"
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

### API Server

```bash
# Local-only (default): requests from 127.0.0.1 are allowed without a key
uvicorn fusion_health.api.app:app --host 127.0.0.1 --port 11469

# Expose to network: API key is REQUIRED — remote requests without it get 401
FUSION_HEALTH_API_KEY=your-secret uvicorn fusion_health.api.app:app --host 0.0.0.0 --port 11469
```

> Security: when `FUSION_HEALTH_API_KEY` is unset, `/api/*` endpoints accept only localhost (`127.0.0.1`/`::1`) requests; non-localhost requests return 401. To serve on `0.0.0.0` or any non-loopback bind, always set `FUSION_HEALTH_API_KEY`. Clients send it via the `X-API-Key` header.

### Lifecycle Manager (start.sh)

Background-detach start/stop/status for fusion-studio integration — port 11469 (moved off 11456 to avoid collision with fusion-simulation-metrics).

```bash
./start.sh start    # nohup uvicorn ... --host 127.0.0.1 --port 11469 (PID file .fusion-health.pid)
./start.sh stop     # graceful SIGTERM, fallback SIGKILL after 5s
./start.sh status   # prints "running (pid N, port 11469)" / "stopped"; exit 0/1
./start.sh restart  # stop then start
```

Override defaults via env: `FUSION_HEALTH_PORT`, `FUSION_HEALTH_HOST`.

### fusion-gateway Integration

fusion-health connects to **fusion-gateway** (port `11432`), which proxies to the local fusion-mlx inference engine. The gateway authenticates with an API key — no route header needed:

```bash
export FUSION_HEALTH_MLX_URL=http://localhost:11432/v1      # fusion-gateway endpoint (default)
export FUSION_MLX_API_KEY=<your-gateway-key>                 # gateway API key (e.g. fg-admin-key)
```

`FUSION_MLX_API_KEY` is the standard key source; `FUSION_HEALTH_MLX_API_KEY` is accepted as an alias. If neither env var is set, fusion-health automatically reads the key from `~/.fusion-mlx/settings.json` (`auth.api_key`) so direct-mlx setups work out of the box. To bypass the gateway and connect to fusion-mlx directly (port `11434`), also set `FUSION_HEALTH_MLX_ROUTE=chat` to send the required `X-Fusion-Route` header.

### Multi-turn Chat

```bash
# Start interactive chat session
fusion-health chat --system-prompt="You are a medical AI assistant"

# Continue a saved session
fusion-health chat --session=saved_session.json
```

### Batch Processing

```bash
# Process all .txt files in a directory
fusion-health batch --dir=./cases --action=ehr_summary --output-dir=./results

# Available actions: ehr_summary, ehr_vitals, code_icd10, compliance_audit, tcm_analyze
# Control concurrency with --concurrency (default: 3)
```

### Template Rendering

```bash
# List available templates
fusion-health template list

# Render a template with data
fusion-health template render discharge_summary --data='{"patient_name":"张三","diagnosis":"高血压","hospital_course":"降压治疗"}'

# Initialize default templates in custom directory
fusion-health template init --dir=./my_templates
```

### TUI (Terminal UI)

```bash
# Launch interactive terminal interface
fusion-health tui
```

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/ehr/summary` | Generate clinical summary |
| `POST` | `/api/v1/ehr/summary/stream` | SSE stream clinical summary |
| `POST` | `/api/v1/ehr/discharge` | Generate discharge summary |
| `POST` | `/api/v1/ehr/discharge/stream` | SSE stream discharge summary |
| `POST` | `/api/v1/ehr/vitals` | Extract vital signs |
| `POST` | `/api/v1/insurance/icd10` | Suggest ICD-10 codes |
| `POST` | `/api/v1/insurance/icd10/stream` | SSE stream ICD-10 codes |
| `POST` | `/api/v1/insurance/cpt` | Suggest CPT codes |
| `POST` | `/api/v1/insurance/cpt/stream` | SSE stream CPT codes |
| `POST` | `/api/v1/insurance/claim-audit` | Audit insurance claim |
| `POST` | `/api/v1/insurance/drg` | Suggest DRG groups |
| `POST` | `/api/v1/insurance/catalog` | Match insurance catalog |
| `POST` | `/api/v1/insurance/procedure-codes` | Suggest procedure codes (ICD-9-CM-3) |
| `POST` | `/api/v1/literature/search` | Search clinical literature |
| `POST` | `/api/v1/literature/evidence` | Summarize evidence |
| `POST` | `/api/v1/literature/evidence/stream` | SSE stream evidence summary |
| `POST` | `/api/v1/compliance/audit` | Audit documentation |
| `POST` | `/api/v1/compliance/audit/stream` | SSE stream audit |
| `POST` | `/api/v1/compliance/regulatory` | Check regulatory compliance |
| `POST` | `/api/v1/compliance/regulatory/stream` | SSE stream regulatory check |
| `POST` | `/api/v1/tcm/analyze` | TCM full analysis |
| `POST` | `/api/v1/tcm/analyze/stream` | SSE stream TCM analysis |
| `POST` | `/api/v1/tcm/syndrome` | Identify TCM syndromes |
| `POST` | `/api/v1/tcm/formula` | Recommend TCM formulas |
| `POST` | `/api/v1/tcm/contraindications` | Check herb contraindications |
| `POST` | `/api/v1/chat/start` | Start chat session |
| `POST` | `/api/v1/chat/message` | Send chat message |
| `POST` | `/api/v1/chat/message/stream` | SSE stream chat response |
| `POST` | `/api/v1/chat/save` | Save chat session |
| `GET` | `/api/v1/chat/sessions` | List active sessions |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete chat session |

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
| `chat [--session] [--system-prompt]` | Interactive multi-turn chat |
| `batch --dir --action [--output-dir] [--concurrency]` | Batch process files |
| `template list` | List available templates |
| `template render <name> --data` | Render template with data |
| `template init [--dir]` | Initialize default templates |
| `tui` | Launch terminal UI |
| `version` | Show version |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Fusion-Health Interface Layer                       │
│  CLI · TUI · Chat · Batch · Template · API (FastAPI REST + SSE)  │
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
│  │ + FHIRMapper   │  │ + ICDValidator │  │ + PubMedClient   │  │
│  └────────────────┘  └────────────────┘  │ + SemanticScholar│  │
│                                           └──────────────────┘  │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐ │
│  │ ComplianceChecker    │  │ TCMAssistant                    │ │
│  │ + RuleEngine         │  │ · syndrome · formula · 十八反   │ │
│  └──────────────────────┘  └─────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ ConversationMem  │  │ BatchProcessor   │  │ TemplateEngine│ │
│  │ · multi-turn     │  │ · concurrency    │  │ · Jinja2      │ │
│  │ · save/load      │  │ · 5 actions      │  │ · 3 builtins  │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LLMGateway · HealthConfig · Pydantic Schemas · SSE Stream │  │
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

[Apache License 2.0](LICENSE)

## Acknowledgments

- [fusion-mlx](https://github.com/dahai80/fusion-mlx) — Apple Silicon model serving
- [Claude Health](https://www.anthropic.com/healthcare) — Reference architecture