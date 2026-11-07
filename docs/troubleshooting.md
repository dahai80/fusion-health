---
doc_id: fusion-health/troubleshooting
product: fusion-health
class: app
entry: service
doc_type: troubleshooting
title: { zh: "故障排查", en: "Troubleshooting" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - start.sh
  - fusion_health/api
---

# Troubleshooting (故障排查)

## Service won't start (服务启动失败)

1. Read `logs/stderr.log` — start.sh writes startup errors there.
2. `port 11469 already in use` — start.sh refuses to start (v1.2.4 self-check).
   Find the holder with `lsof -i :11469` or change `FUSION_HEALTH_PORT`.
3. `venv not found` — start.sh uses `FUSION_HEALTH_VENV` (default
   `/Users/dahai/fusion/.venv`); point it at your venv if different.
4. Stale PID file (`status` says running, port closed): `rm .fusion-health.pid`
   and start again.
5. Import error for fastapi/uvicorn: install the `[api]` extra —
   `pip install -e ".[all]"`.

## 401 errors (鉴权报错)

- `FUSION_HEALTH_API_KEY` set but the client omits `X-API-Key` → add the header.
- Key unset but you call from a non-loopback address → loopback-only by design;
  set the key or call from 127.0.0.1.
- Gateway auth errors during generation: the gateway key resolution order is
  `FUSION_MLX_API_KEY` → alias `FUSION_HEALTH_MLX_API_KEY` →
  `~/.fusion-mlx/settings.json` (`auth.api_key`). Export one of them; direct-mlx
  setups also need `FUSION_HEALTH_MLX_ROUTE=chat` (v1.2.5 fixed the
  direct-mlx auth regression from key-priority handling).

## LLM calls fail or degrade (模型调用失败)

1. `curl http://localhost:11432/v1/models` (gateway) or
   `curl http://127.0.0.1:11434/api/v1/models` (direct) — is a model loaded?
2. Start the engine: `~/fusion/fusion-mlx/start.sh start`, then load a model.
3. Slow/truncated output: tune `FUSION_HEALTH_TIMEOUT` and
   `FUSION_HEALTH_MAX_TOKENS`.
4. deprecated port warning in logs: `FUSION_HEALTH_API_PORT` is legacy — set
   `FUSION_HEALTH_PORT` instead.

## Literature search fails (文献检索失败)

- PubMed / Semantic Scholar need internet access. On an offline box set
  `FUSION_HEALTH_OFFLINE=1` or disable each client
  (`FUSION_HEALTH_PUBMED_ENABLED=0`, `FUSION_HEALTH_S2_ENABLED=0`).
- What is sent to these sites: the search query only, never patient data —
  see `DATA_SOURCES.md`.

## Audit / compliance issues (审计与合规)

- `GET /api/v1/audit/verify` reports a broken chain: audit files were edited
  outside the app. Do not hand-edit audit entries; restore from backup or
  rotate `FUSION_HEALTH_AUDIT_HMAC_KEY` deliberately (invalidates old links).
- HMAC key missing: without it the chain is unverified; keep the key in
  `~/.fusion-health/env` so start.sh loads it every boot.

## CLI issues (CLI 问题)

- `fusion-health: command not found` — the venv is not activated:
  `source /Users/dahai/fusion/.venv/bin/activate`.
- Batch stops on one file: batch continues per-file; failures are reported in
  the run summary. Check `--output-dir` writability and per-file encoding
  (UTF-8 expected).
- Template render error: run `fusion-health template list` first — render
  requires a template name from that list and valid JSON in `--data`.

## Logs (日志)

- `logs/stdout.log`, `logs/stderr.log` — lifecycle + request errors.
- Request logs are PHI-redacted (`crypto.py`, `logging_config.py`); if you see
  raw identifiers in logs, report it — that is a defect, not expected behavior.
