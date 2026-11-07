---
doc_id: fusion-health/api-reference
product: fusion-health
class: app
entry: service
doc_type: api-reference
title: { zh: "API 参考", en: "API Reference" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - README.md
  - fusion_health/api/routes
  - docs/api.md
---

# API Reference (API 参考)

Base URL: `http://127.0.0.1:11469`. Full endpoint table lives in README
"API Endpoints"; this page maps the surface and the auth/streaming contract.

## Auth (鉴权)

- `FUSION_HEALTH_API_KEY` unset: `/api/*` accepts only loopback clients
  (`127.0.0.1` / `::1`); non-loopback gets 401.
- Set: every client sends `X-API-Key: <key>`. `/api/v1/health` is public and
  requires no key.

未设置 Key 时仅回环可访问；设置后所有客户端需带 `X-API-Key`（health 除外）。

## REST + SSE surface (端面)

| Group | Endpoints | Streaming |
|---|---|---|
| health | `GET /api/v1/health` | — |
| ehr | `/ehr/summary`, `/ehr/discharge`, `/ehr/vitals` | summary/discharge have `/stream` (SSE) |
| insurance | `/insurance/icd10`, `/insurance/cpt`, `/insurance/claim-audit`, `/insurance/drg`, `/insurance/catalog`, `/insurance/procedure-codes` | icd10/cpt have `/stream` |
| literature | `/literature/search`, `/literature/evidence` | evidence has `/stream` |
| compliance | `/compliance/audit`, `/compliance/regulatory` | both have `/stream` |
| tcm | `/tcm/analyze`, `/tcm/syndrome`, `/tcm/formula`, `/tcm/contraindications` | analyze has `/stream` |
| chat | `/chat/start`, `/chat/message`, `/chat/save`, `GET /chat/sessions`, `DELETE /chat/sessions/{id}` | message has `/stream` |
| audit | `GET /api/v1/audit/verify` | HMAC-chain verification (v1.2.6) |

- SSE responses emit token-by-token delta events and a terminal done/error
  event (`fusion_health/api/sse.py`).
- Request/response schemas are Pydantic models in `fusion_health/schemas/`;
  route modules in `fusion_health/api/routes/` are the exact source.

SSE 逐 token 增量推送并以 done/error 事件收尾；具体字段以 `fusion_health/schemas/` 为准。

## Web console (Web 控制台)

`GET /ui` serves the static console (`fusion_health/api/static/index.html`),
backed by the same `/api/v1` surface. Assets mount at `/ui/assets`.

## Python client API (Python 调用层)

For in-process use without HTTP (`docs/api.md` has the full method tables):

```python
from fusion_health.ehr.processor import EHRProcessor            # summary, discharge, vitals
from fusion_health.insurance.coder import InsuranceCoder        # icd10, cpt, claim audit
from fusion_health.literature.retriever import LiteratureRetriever, ComplianceChecker
```

## Rate limits and sessions (限流与会话)

- `FUSION_HEALTH_RATE_LIMIT_RPM` caps requests per minute (in-process limiter).
- Chat sessions expire after `FUSION_HEALTH_SESSION_TTL` seconds; `GET
  /api/v1/chat/sessions` lists live ones.
