---
doc_id: fusion-health/guide
product: fusion-health
class: app
entry: service
doc_type: guide
title: { zh: "Claude Code 工作指引", en: "Claude Code Working Guide" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - CLAUDE.md
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fusion-Health is a local AI healthcare assistant: EHR summarization, medical coding (ICD-10/CPT + China-specific DRG/catalog/ICD-9-CM-3), clinical literature retrieval, documentation/regulatory compliance, and TCM syndrome/formula analysis. All LLM inference runs locally via the OpenAI-compatible API at `http://127.0.0.1:11434/v1/chat/completions` (fusion-mlx direct). No cloud AI calls.

## Development Commands

```bash
# Activate env first (monorepo shares one .venv at repo root)
source .venv/bin/activate

# Install with extras (api/tui/test/all); fusion-core must be installed first
pip install -e fusion-core && pip install -e ".[test]"

# Run all tests
pytest

# Coverage
pytest --cov=fusion_health tests/

# Single test file / test
pytest tests/test_core.py
pytest tests/test_core.py::test_ehr_summary -v

# Real-model regression suite (requires fusion-mlx running + a loaded model)
FUSION_HEALTH_REAL_MODEL=1 pytest tests/test_real_model.py -v

# Lint (config: select F/E/W, ignore E501; no format-check in CI — 35 files pre-existing unformatted)
ruff check .

# API server (port 11469 — moved off 11456, which belongs to fusion-simulation-metrics)
uvicorn fusion_health.api.app:app --host 127.0.0.1 --port 11469
./start.sh start|stop|status|restart   # nohup detach, PID file .fusion-health.pid; since v1.2.4 start self-checks port-registry.yaml entry (FUSION_SKIP_REGISTRY_CHECK=1 bypasses, FUSION_REGISTRY overrides path); sources ~/.fusion-health/env with set -a for persistent secrets (FUSION_HEALTH_AUDIT_HMAC_KEY etc., FUSION_HEALTH_ENV_FILE overrides path)

# CLI (entry point: fusion-health = fusion_health.cli:main)
fusion-health ehr summary --input=notes.txt --output=out.json
fusion-health code icd10 --input="hypertension and diabetes"
fusion-health cn-code drg --input=note.txt          # China: drg | catalog | icd9cm3
fusion-health tcm analyze --input=note.txt          # analyze | syndrome | formula
fusion-health literature "diabetes treatment guidelines" --max-results=10
fusion-health compliance audit --input=note.txt
fusion-health eval --report=eval.json               # clinical coding golden-set evaluation
fusion-health tui
fusion-health chat --system-prompt="..."
fusion-health batch --dir=./cases --action=ehr_summary --output-dir=./out
fusion-health template list|render|init
python -m fusion_health.cli ...   # if entry point not installed

# Start/stop fusion-mlx (required for real model integration tests)
~/claude-home/fusion-mlx/start.sh start|stop

# Ops scripts (scripts/)
python scripts/backup.py          # DR backup of sessions/data
python scripts/load_test.py       # HTTP load test against the API
python scripts/ingest_data.py     # Ingest real datasets (replaces sample-data marker)
```

## Architecture

### Core Engine — domain classes

All share one pattern: async methods that call `LLMGateway.chat()`/`chat_stream()`, parse the LLM's JSON/text response, and return a fallback on any error (never raise).

| Class | Module | Responsibility |
|---|---|---|
| `EHRProcessor` | `ehr/processor.py` | Clinical summaries, discharge summaries, vitals extraction |
| `FHIRMapper` | `ehr/fhir_mapper.py` | Map structured output to FHIR resources |
| `InsuranceCoder` | `insurance/coder.py` | ICD-10/CPT suggestions, claim auditing |
| `ICDValidator` | `insurance/icd_validator.py` | Validate/score ICD codes |
| `CNMedicalCoder`, `DRGHelper`, `InsuranceCatalogMatcher`, `ICD9CM3Validator` | `insurance/cn_coding.py` | China-specific coding: DRG grouping, insurance catalog match, ICD-9-CM-3 procedures |
| `LiteratureRetriever` | `literature/retriever.py` | Literature search + evidence summarization |
| `PubMedClient`, `SemanticScholarClient` | `literature/pubmed_client.py`, `literature/semantic_scholar.py` | Real literature backends (disable via `FUSION_HEALTH_PUBMED_ENABLED=0`) |
| `ComplianceChecker` | `compliance/checker.py` | Documentation & regulatory compliance auditing (NOT in `literature/` anymore) |
| `RuleEngine` | `compliance/rule_engine.py` | YAML rule-driven compliance checks |
| `TCMAssistant` | `tcm/assistant.py` | TCM syndrome identification, formula recommendation, 十八反 contraindication check |
| `ConversationSession`, `ConversationMemory` | `conversation.py` | Multi-turn chat with save/load |
| `BatchProcessor` | `batch.py` | Concurrent batch processing (5 actions) |
| `TemplateEngine` | `templates.py` | Jinja2 template rendering (3 builtins) |
| `ArtifactClient` | `artifact_client.py` | Talk to fusion-artifacts-engine |

### Enterprise hardening (v1.2.0+)

| Module | Responsibility |
|---|---|
| `crypto.py` | PHI AES-256-GCM at-rest encryption (key from `FUSION_HEALTH_ENC_KEY`, derived via scrypt; `encryption_enabled()` gates it) |
| `audit.py` | Tamper-evident HMAC-chained access log (`log_access`, `verify_log_file`, `rotate_log`); PHI hashed, never logged plaintext. Exposed via `api/routes/audit.py`: `GET /api/v1/audit/verify` + `GET /api/v1/audit/recent` (v1.2.6) |
| `enterprise.py` | `production_readiness_check(config)` / `assert_enterprise_ready()` — fails on sample-data marker, missing key/encryption in prod mode |
| `clinical_eval.py` | Golden-set clinical coding evaluation (CLI `eval`) |

### Interface Layer

- **CLI** (`cli/__init__.py`): argparse with subcommands `ehr`, `code`, `literature`, `compliance`, `tui`, `chat`, `batch`, `template`, `version`. Each lazy-imports its class, runs async via `asyncio.run()`.
- **TUI** (`cli/tui.py`): textual/rich interactive mode.
- **API** (`api/app.py`): FastAPI factory `create_app()` with lifespan config injection. Routers under `api/routes/`: `health`, `ehr`, `insurance`, `literature`, `compliance`, `tcm`, `chat`, `metrics` — all mounted under `/api/v1/*`. Six routes expose SSE streaming via `api/sse.py` (paths end in `/stream`).
- **`gateway_provider.py`**: process-wide pooled `LLMGateway` singleton (`get_gateway(config)` / `close_gateway()`), created in the app lifespan and used by all routes — never construct `LLMGateway` per-request.

### Cross-cutting

- **`LLMGateway`** (`llm_gateway.py`): single LLM client for every domain class. `chat()` returns `LLMResult` (schemas/base.py); `chat_stream()` yields tokens. `_auth_headers()` sends `Authorization: Bearer <key>` (only if `mlx_api_key` set) and `X-Fusion-Route` (only if `mlx_route` set) — both per-request, not baked into the pooled client.
- **`HealthConfig`** (`config.py`): dataclass loaded by `from_env()`. Resolution order: env vars → `~/.fusion-health/config.yaml` overrides → auto-read API key from `~/.fusion-mlx/settings.json` (`auth.api_key`) when no key env var set.

## Key Design Points

- **Model is configurable**: default `Qwen3.5-9B-4bit` (was hardcoded `qwen3.5-9b`; fixed). Override via `FUSION_HEALTH_MODEL` or `--model`. Endpoint via `FUSION_HEALTH_MLX_URL`. Model id is resolved at first LLM call: `LLMGateway._resolve_model()` queries `/models`, fuzzy-matches shorthand → full backend id (e.g. `Qwen3.5-9B-4bit` → `mlx-community--Qwen3.5-9B-4bit`), cached per gateway instance. If not found, keeps requested id as-is and the backend 404 surfaces a clear hint.
- **fusion-gateway topology**: default `mlx_url` is `http://127.0.0.1:11434/v1` (fusion-mlx direct, IPv4 to avoid OrbStack/IPv6 hijack of `localhost`). The auto-loaded key from `~/.fusion-mlx/settings.json` is the mlx key, valid for 11434 but rejected by fusion-gateway 11432 (which has its own `api_keys`). `X-Fusion-Route` is NOT required by mlx 0.8.80. Gateway override: set `FUSION_HEALTH_MLX_URL=http://127.0.0.1:11432/v1` + a gateway key in `FUSION_MLX_API_KEY`.
- **API key sources** (v1.2.3+, via `fusion_core.config`): `FUSION_CLIENT_KEY` (canonical) → `FUSION_MLX_API_KEY`/`MLX_API_KEY` (deprecated, warn) → `~/.fusion-mlx/settings.json` `auth.api_key` (auto-read, zero-env). Resolution lives in fusion-core only (`config.py:_mlx_key()` routes; no local `def _resolve*key`). `FUSION_PROFILE=prod` + missing key = RuntimeError; dev = "" + warn-once. The auto-loaded key is the mlx key — works against 11434 (default), NOT 11432 (gateway). Port: `FUSION_HEALTH_PORT` canonical (matches start.sh), `FUSION_HEALTH_API_PORT` deprecated.
- **API auth** (`api/middleware.py` `APIKeyMiddleware`): exempt `/api/v1/health`, `/docs`, `/openapi.json`, `/redoc`. When `FUSION_HEALTH_API_KEY` unset, `/api/*` accepts only localhost (`127.0.0.1`/`::1`/`localhost`); non-localhost → 401. When set, clients send `X-API-Key` header (constant-time `hmac.compare_digest`). This prevents 0.0.0.0 exposure without a key. Same middleware does owner-isolated rate limiting (`RateLimiter` — shared SQLite backend when writable, else in-memory per-process), per-path normalization, and attaches the medical disclaimer to API responses.
- **fusion-core http_client adoption**: `LLMGateway` borrows `fusion_core.http_client` — `get_async_client` (LRU connection pool, keyed by loop_id:base_url) for client reuse and `with_retry` (429/500/502/503/504 + connect/timeout, exponential backoff) on the `chat()` path. Route headers + API key passed per-request (avoid cross-instance header leakage). `chat_stream` keeps raw `httpx.stream` (SSE, no retry). `close()` releases the reference but does not close the shared pooled client (pool-managed lifecycle).
- **D-H3 empty-content guard**: `chat()` treats a 200 response with empty/whitespace `content` as a failure — returns `LLMResult(content="", error="empty_content")` instead of a silent empty success. Preserves the `if result.error:` field-check semantics so all callers are unchanged.
- **Pydantic IS used**: `schemas/` package holds `LLMResult` (base) plus ehr/insurance/literature/compliance/fhir models. `chat(response_schema=...)` validates via `schema.model_validate()`. Fenced ```json blocks are stripped before parse.
- **Error handling**: every async method returns an error dict/`LLMResult` rather than raising. Test assertions must account for this.

## Testing Approach

Most tests mock `LLMGateway.chat`/`chat_stream` at the caller boundary (above httpx). A few `TestLLMGateway` tests mock `_get_client` to exercise the real `chat()` path (e.g. D-H3 empty-content guard). API tests use `TestClient`/`ASGITransport` with `X-API-Key` header + env fixtures. No running fusion-mlx server needed for unit tests. Real model tests (per global instructions) live in `tests/test_real_model.py`, skip-gated behind `FUSION_HEALTH_REAL_MODEL=1` with fusion-mlx running; models download via `https://hf-mirror.com`.

Coverage floor is 80% (`[tool.coverage.report] fail_under = 80`); TUI and `cli/__main__.py` are omitted.

CI (`.github/workflows/ci.yml`): matrix macOS-14 + ubuntu-22.04, Python 3.12, installs fusion-core from git (not on PyPI — see dahai80/fusion-core#9), then `ruff check .` → pytest with coverage (80% floor enforced) → `pip-audit` → `bandit -r fusion_health`.

## Operational rules (from AGENTS.md)

`AGENTS.md` defines cross-fusion-repo engineering rules that apply here: ports must be registered in `/Users/dahai/fusion/architecture/port-registry.yaml` before binding (API is on 11469); new serve/daemon entrypoints must set their process title via `setproctitle` (format `fusion-health serve :11469`); cross-repo issues must document source repo, contract, and blocking relationship, with a comment on the parent issue. Never modify another fusion-* repo's source — file an issue upstream instead.
