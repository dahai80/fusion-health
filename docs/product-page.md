---
doc_id: fusion-health/product-page
product: fusion-health
class: app
entry: service
doc_type: product-page
title: { zh: "Fusion-Health 产品页", en: "Fusion-Health Product Page" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - README.md
  - pyproject.toml
  - start.sh
  - fusion_health/api
---

# Fusion-Health Product Page (产品页)

## What it is (产品定位)

Fusion-Health is a local AI healthcare assistant powered by fusion-mlx. It
processes medical records, generates clinical summaries, suggests
ICD-10/CPT/DRG codes, searches clinical literature, audits compliance, and
provides TCM analysis — entirely local, no data leaves the device.

Fusion-Health 是基于 fusion-mlx 的本地医疗 AI 助手：处理病历、生成临床摘要、
推荐 ICD-10/CPT/DRG 编码、检索临床文献、合规审查与中医辨证分析——全部本地运行，
数据不出设备。

## Grid position (契约网格)

| Key | Value | Evidence (证据) |
|---|---|---|
| class | app | Domain application in the fusion monorepo |
| entry | service | Lifecycle via `start.sh` (REST on :11469, fusion-studio auto-start); the v1.2.6 web console is a small static page served by the same FastAPI app at `/ui`, auxiliary to the REST API + CLI surfaces |

## What users no longer have to do (用户不再需要做什么)

- No more manual ICD-10/CPT code lookup: `InsuranceCoder` suggests codes from
  free text with validation. Constraint: suggestions are decision support;
  a human coder still signs off before billing submission.
- No more structuring notes by hand: `EHRProcessor` produces summaries,
  discharge documents, and vital extraction from raw clinical text.
  Constraint: output quality tracks the loaded local model; small models
  miss details on long notes.
- No more separate PHI scrubbing pipeline: audit entries are HMAC-chained and
  verifiable via `GET /api/v1/audit/verify`; secrets persist only in the
  operator-owned env file. Constraint: the chain proves tamper-evidence, not
  accuracy of the underlying analysis.

- 不再手工查编码：模型直接从文本推荐 ICD-10/CPT（仍需人工签核后方可计费）。
- 不再手工结构化病历：摘要/出院记录/生命体征抽取均由 EHRProcessor 完成。
- 不再单独搭脱敏审计管线：审计条目 HMAC 链式且可校验；约束是链只证明防篡改，
  不证明分析正确性。

## Key capabilities (核心能力)

- Interfaces: CLI (`fusion-health`), terminal UI (`fusion-health tui`,
  `[tui]` extra), REST + SSE API (32 endpoints under `/api/v1/*`), static web
  console at `/ui`, batch processing (5 actions, concurrency control), Jinja2
  templates (3 built-ins).
- Domains: EHR (summary/discharge/vitals + FHIR mapping), insurance coding
  (ICD-10/CPT/DRG/claim audit/catalog/procedure codes), literature (PubMed +
  Semantic Scholar), compliance (documentation + regulatory), TCM (syndrome,
  formula, herb contraindications), multi-turn chat with session save/load.
- Ops: HMAC-chained audit log with verification endpoint, rate limiting (RPM),
  session TTL, offline mode, PHI-safe logging.

## Interfaces (入口)

| Interface | How | Source |
|---|---|---|
| REST + SSE API | `./start.sh start` → `http://127.0.0.1:11469/api/v1/*` | `start.sh`, `fusion_health/api/app.py` |
| CLI | `fusion-health <command>` | `pyproject.toml [project.scripts]` |
| TUI | `fusion-health tui` | `fusion_health/cli/tui.py` |
| Web console | `http://127.0.0.1:11469/ui` | `fusion_health/api/static/` |

## Non-goals (边界)

- Not a diagnostic device and not cloud-hosted: outputs are decision support;
  no PHI is transmitted off-device (literature search sends queries, not
  patient data — see `DATA_SOURCES.md`).
- 非诊断设备、非云服务；文献检索只发送查询词，不发送患者数据。

## Status (状态)

v1.2.6. History in README "Changelog" section; compliance posture in
`COMPLIANCE.md`, `REGULATORY.md`, `LEGAL.md`.
