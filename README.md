<div align="center">

# Fusion-Health

**Local AI Healthcare Assistant — Powered by fusion-mlx**

Process medical records, generate clinical summaries, suggest ICD-10/CPT codes, search clinical literature, and check compliance — entirely local, no data leaves your device.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-148-success.svg)](tests/)

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

## Changelog

### v1.2.0rc1 — Product-Readiness Audit P0–P3 Remediation (Release Candidate)

A third product-readiness audit (5 P0, 12 P1, 20 P2, ~12 P3) found fusion-health not publishable for enterprise use. All findings fixed:

**P0 (blocking):**
- Structured logging (JSON + rotating file handler) via `configure_logging()` in API lifespan
- HMAC-SHA256 per-line audit log signing + sequence counter + `verify_log_line()` + `0o600` perms
- Config env/YAML cast error tolerance (keep default + warn on bad input)
- API audit logging on all routes (`log_access` on every endpoint)
- CORS locked down (origins from env, methods/headers restricted)
- `/api/v1/metrics` route (request/auth/rate-limit counters)
- `start.sh` API-key enforcement warning + port-in-use pre-check + `doctor` subcommand

**P1 (severe):**
- CPT validator returns `ai_suggested` for format-valid codes (was hard `invalid`)
- ICD-10 subcode regex `{1,4}`→`{1,7}` (real codes truncated)
- CLI `tcm` + `cn-code` subcommands (DRG/catalog/ICD-9-CM-3 + syndrome/formula)
- SSE stream routes prepend domain system prompts (EHR/insurance/compliance/TCM)
- Rate limiter fixed (`deque` + `popleft`, default 60 rpm)
- Session reaper extracted to lifespan (saves before close on eviction/shutdown)
- Health `/ready` endpoint (data-file status + session count)
- Literature search result cache (10-min TTL)
- Shared pooled LLMGateway singleton (all stream routes reuse one pooled httpx client; lifecycle in API lifespan — fixes per-request gateway churn + connection lifecycle)
- Multi-worker rate-limit warning (`FUSION_HEALTH_WORKERS` env; per-process limiter logs effective N×rpm when >1 worker)

**P2 (medium):**
- FHIR mapper uses `model_dump()` (removed dead `import json`)
- Bank card regex tightened (issuer-prefix aware)
- TCM herb load mtime invalidation (was permanent cache)
- ICD/DRG/catalog/ICD-9-CM-3 responses marked `data_source` from `.data_source` marker file (flips `sample`→`full` on ingestion)
- Batch processor root-confinement + dead `ACTION_MAP` removed
- CI: Linux matrix + coverage 80% floor + pip-audit

**Non-code delivery:**
- `scripts/ingest_data.py` — validates + installs authoritative coding datasets (ICD-10-CN / ICD-9-CM-3 / DRG / insurance catalog), flips `.data_source` marker to `full`, backs up samples. See [DATA_SOURCES.md](DATA_SOURCES.md).
- `DATA_SOURCES.md` — dataset status, required columns, ingestion + rollback steps, production gate.
- `COMPLIANCE.md` — PHI data flow, audit logging, retention, deployment hardening checklist, operator responsibilities (PIPL / HIPAA-aligned).
- Multi-worker shared rate limiting via `FUSION_HEALTH_RATE_LIMIT_DB` (SQLite backend, atomic `BEGIN IMMEDIATE` count-and-insert; in-memory fallback warns when >1 worker).
- AES-256-GCM at-rest encryption for conversation PHI (`FUSION_HEALTH_PHI_KEY`: 64-hex raw key or passphrase→PBKDF2-HMAC-SHA256 200k iters; plaintext fallback when unset, backward-compatible). See `fusion_health/crypto.py`.
- Enterprise production-readiness gate (`fusion_health/enterprise.py`): set `FUSION_HEALTH_ENTERPRISE=1` to enforce at API startup — checks data source is `full`, API key / audit HMAC key / PHI encryption key / CORS origins all set; logs per-check failures. `FUSION_HEALTH_ENTERPRISE_HARD=1` refuses startup on any failure (soft mode = warn only). `/api/v1/health/ready` reports `enterprise_ready` + `enterprise_failures`.

**Enterprise commercial-release hardening:**
- Security scanning in CI — Bandit SAST (`bandit -r fusion_health`, must be clean) + pip-audit dependency CVE scan, both enforced (non-zero exit on findings). See [SECURITY.md](SECURITY.md).
- `X-Fusion-Disclaimer` response header on every API response + CLI startup log: advisory-only, not a diagnosis, not NMPA-registered.
- Audit log rotation + integrity verification (`audit.rotate_log`, `audit.verify_log_file` — detects HMAC tamper + sequence gaps).
- DR backup/restore — `scripts/backup.py create|verify`: backs up audit log + conversation sessions into a sha256-manifested tar.gz; **aborts backup if audit log is tampered**; `verify` checks every file's hash against the manifest (no auto-restore — operator copies manually for PHI safety).
- Load/performance test — `scripts/load_test.py` (in-process ASGI, no network) + `tests/test_load.py` (CI): concurrency 10-20, measures p50/p95/p99 + throughput, SLO gate p95 ≤ 2000ms (`FUSION_HEALTH_LOAD_SLO_MS`). Measured: 316 req/s, p95=84ms.
- Clinical evaluation toolkit — `fusion_health/clinical_eval.py` golden-set harness (precision/recall/F1, 3-char ICD category matching) + `fusion-health eval` CLI. Verified against live model: 5/5 cases hit, recall=1.00, F1=0.91. Real-model test gated by `FUSION_HEALTH_REAL_MODEL=1`.
- [REGULATORY.md](REGULATORY.md) — NMPA medical-device classification + Class II registration path + required human actions (consultant, QMS, clinician-verified golden set ≥100 cases).
- [LEGAL.md](LEGAL.md) — Terms-of-use template, PIPL-aligned DPA, PIPIA template, liability framework. Requires lawyer review before use.

### v1.1.0 — Second Independent Architecture Audit Fixes

A second independent architect audit found 6 P0, 9 P1, 10 P2, and several P3 issues across architecture boundaries, runtime risk, and engineering implementation. All P0, P1 (except deferred R9), and P2 fixed.

**Architecture P0 (H1–H6)**
- Chat sessions now TTL-bounded (`FUSION_HEALTH_SESSION_TTL`, default 1800s) with a background reaper that evicts stale sessions every 300s — fixes unbounded in-memory session growth.
- Rate limiting via token-bucket `RateLimiter` (`FUSION_HEALTH_RATE_LIMIT_RPM`) — per-owner 429 with `retry_after`, no unbounded API exposure.
- Structured PHI access audit logging (`fusion_health/audit.py`): records owner, method, path, action, status, `phi_input_hash` (sha256[:16]) + length — never raw PHI. JSON-lines append, thread-locked, disable via `FUSION_HEALTH_AUDIT_DISABLED=1`.
- CORS middleware ordered outermost (added after `APIKeyMiddleware`) + OPTIONS passthrough — preflight no longer blocked by auth.
- Lifespan no longer discards injected config: `create_app(config)` survives startup; shutdown closes all chat sessions + literature clients.
- `/api/v1/health` now probes MLX backend `/models` (httpx, 5s timeout) and returns 503 `degraded` with backend error when unreachable — no false-healthy when inference is down.

**Runtime Risk P1 (H7–H9, R1–R6)**
- Validator DB caches (`ICDValidator`, `ICD9CM3Validator`, `DRGHelper`, `InsuranceCatalogMatcher`) now mtime-based invalidation — file edits picked up without process restart.
- ICD-10/CPT validation three-state: `verified` (DB hit), `unverified` (format-valid, not in DB), `invalid` (format-mismatch) — no false-positive `valid=True` on format match alone.
- PHI redaction in LLM gateway logs: decode/schema/validation errors log `content_len` and `status_code`, never raw `content`/`response.text`.
- SSE stream error path raises instead of emitting a synthetic error token; client-disconnect path emits `interrupted` and skips `on_done` — truncated content no longer persisted as a complete reply.
- Prompt-injection anchors: system prompts (`SYSTEM_PROMPT` + `_messages()`) added to EHR, coding, compliance, and TCM LLM calls.
- Conversation context budget: `get_messages` trims by `max_context_chars` (default 96000), preserving system messages — bounded token growth.

**Engineering P2 (R7–R10, E2–E6)**
- TCM herb normalization + negation-aware contraindication match (4-char window + phrase set) — reduces false 十八反 matches.
- Compliance rule engine `required` field check requires label boundary — no substring false positives.
- Literature stream prompt built from joined text, not list repr.
- `close_all_sessions` / `close_all_clients` shutdown hooks; per-request retriever `aclose()` in `finally`.
- `import fusion_health` no longer requires fastapi (lazy `__getattr__`).
- Plugin tools cache `HealthConfig` instead of rebuilding per call.

### v1.0.9 — Security & Medical-Safety Audit Fixes

Adversarial audit found 7 blocking items + ~20 P0–P3 issues across security, concurrency, medical safety, and performance. All fixed.

**Security (F1–F4)**
- `APIKeyMiddleware` rewritten: default-deny, path normalization (defeats `//api//...` bypass), owner-id injection (sha256 of key). Non-loopback requests without a key return 401.
- Chat sessions keyed by `(owner_id, session_id)` — one owner cannot read/list/delete another's sessions. `MAX_SESSIONS=1000` with per-owner LRU eviction + gateway close.
- SSE streaming hardened: 15s heartbeat, client-disconnect detection, gateway cleanup in `finally`, `on_done` callback persists the assistant message to history (stream/non-stream history now consistent).
- TCM `analyze` validates LLM output via `TCMAnalysisResult` schema and marks results `ai_generated_unverified` (never presented as authoritative). EHR `ClinicalSummary`/`VitalsResult` carry the same `source` marker + warning log.

**Concurrency & Memory (B1–B6)**
- `ConversationMemory` system-message handling: `add_system_message` updates in place, `_trim_short_term` preserves system messages while evicting oldest user/assistant turns to long-term. `load()` validates message roles and skips malformed entries.
- `BatchProcessor` results/errors are per-run locals (no cross-run leakage); file I/O offloaded to threads.
- Chat session deletion and eviction call `session.close()` (releases LLM gateway).

**Medical Safety (A1–A5)**
- TCM symptom matching handles negation (`不/无/未/没/非/勿/否`) so "无发热" no longer matches "发热".
- ICD/DRG/catalog databases cached at class level per `data_dir` (parsed once per process, not per request) while instances stay per-request for mock compatibility.
- CLI `_safe_input`/`_safe_output` helpers validate paths and create parent dirs.
- SSE routes for ehr/insurance/literature/compliance/tcm pass the gateway to `sse_response` for cleanup.

**Performance (P1–P3)**
- `LiteratureRetriever` fetches PubMed + Semantic Scholar in parallel via `asyncio.gather` (DOI dedup preserved).
- PubMed / Semantic Scholar / Artifact clients use lazy instance-level `httpx.AsyncClient` with `aclose()`.

**Tests (M3)**
- Added `tests/test_audit_security.py`: middleware path bypass, session owner isolation, stream history consistency. 148 tests pass, `ruff check .` clean.

### v1.0.8 — Port Conflict & CI Repair

API port moved 11456 → 11469 (avoids collision with fusion-simulation-metrics, closes #16). CI repaired (ruff + api extras). Dynamic version.

### v1.0.7 — Production Hardening

CI, out-of-box API key, API auth default-on.

---

## License

[Apache License 2.0](LICENSE)

## Acknowledgments

- [fusion-mlx](https://github.com/dahai80/fusion-mlx) — Apple Silicon model serving
- [Claude Health](https://www.anthropic.com/healthcare) — Reference architecture