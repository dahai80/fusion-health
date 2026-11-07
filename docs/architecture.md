---
doc_id: fusion-health/architecture
product: fusion-health
class: app
entry: service
doc_type: architecture
title: { zh: "架构说明", en: "Architecture" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - fusion_health
  - README.md
---

# Architecture (架构说明)

## Module map (模块划分)

Source: `fusion_health/` package layout.

```
fusion_health/
├── cli/              # click CLI + textual TUI (tui.py), __main__.py entry
├── api/              # FastAPI app factory, middleware (auth/rate-limit), sse, routes/, static/ (web console)
├── ehr/              # EHRProcessor (summary/discharge/vitals) + FHIRMapper
├── insurance/        # InsuranceCoder: ICD-10/CPT/DRG/claim audit + ICDValidator
├── literature/       # LiteratureRetriever (PubMed + Semantic Scholar), ComplianceChecker
├── compliance/       # rule engine, YAML rules
├── tcm/              # TCMAssistant: syndrome/formula/contraindications, YAML data
├── conversation.py   # multi-turn memory, session save/load
├── batch.py          # BatchProcessor: 5 actions, concurrency control
├── templates.py      # Jinja2 template engine, 3 built-ins
├── llm_gateway.py    # OpenAI-compatible client -> fusion-gateway / fusion-mlx
├── artifact_client.py# fusion-artifacts-engine export client
├── audit.py          # HMAC-chained audit log + verification
├── crypto.py         # PHI-safe helpers
├── enterprise.py     # enterprise feature flags
├── config.py         # HealthConfig, fusion_core.config single-point resolution
├── schemas/          # Pydantic request/response models
├── data/             # ICD/CPT TSV datasets
└── plugins/          # plugin hooks
```

## Request flow (请求链路)

1. Client (CLI / TUI / REST / web console) → FastAPI on :11469.
2. `api/middleware.py` — loopback-or-API-key check, rate limiting, request
   logging with PHI-safe redaction.
3. Route handler → domain service (ehr / insurance / literature / compliance /
   tcm) → `LLMGateway`.
4. `LLMGateway` → fusion-gateway :11432 (`/v1/chat/completions`) → fusion-mlx
   :11434. Direct-mlx mode sets `X-Fusion-Route: chat` when
   `FUSION_HEALTH_MLX_ROUTE=chat`.
5. Audit: significant operations append HMAC-chained entries; `GET
   /api/v1/audit/verify` re-validates the chain.

链路：客户端 → 中间件（回环/Key 校验、限流、脱敏日志）→ 领域服务 → LLMGateway →
fusion-gateway :11432 → fusion-mlx :11434；审计走 HMAC 链并可经 API 校验。

## Data files (内置数据)

- `fusion_health/data/*.tsv` — ICD-10 / CPT / ICD-9-CM-3 lookup tables.
- `fusion_health/compliance/rules/*.yaml` — documentation compliance rules.
- `fusion_health/tcm/data/*.yaml` — TCM syndrome/formula/contraindication data.
- Templates: 3 built-in Jinja2 templates, exportable via `template init`.

## Failure modes (故障模式)

| Failure | Behavior |
|---|---|
| Gateway/MLX unreachable | LLMGateway request fails with connection error; CLI exits non-zero; SSE emits error event |
| No gateway key found | falls back to `~/.fusion-mlx/settings.json`; if absent, auth error from the gateway (v1.2.5 fixed the direct-mlx auth regression) |
| Port already in use | start.sh refuses to start (v1.2.4 port-registry self-check) |
| External literature sites unreachable | disable via `FUSION_HEALTH_PUBMED_ENABLED=0` / `S2_ENABLED=0` or run `FUSION_HEALTH_OFFLINE=1` |
| Audit chain mismatch | `/api/v1/audit/verify` reports the broken link; investigate local file edits |

## Cross-repo dependencies (跨仓依赖)

- fusion-mlx (:11434) — inference engine.
- fusion-gateway (:11432) — inference front door, API-key auth.
- fusion-core — config resolution + shared HTTP/logging base.
- fusion-artifacts-engine (optional) — artifact export via `FUSION_ARTIFACTS_URL`.
- See `/Users/dahai/fusion/architecture/port-registry.yaml` for port ownership.
