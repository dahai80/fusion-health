---
doc_id: fusion-health/get-started
product: fusion-health
class: app
entry: service
doc_type: get-started
title: { zh: "快速开始", en: "Get Started" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - README.md
  - start.sh
  - pyproject.toml
---

# Get Started (快速开始)

## Prerequisites (前置条件)

- Python 3.12. In the fusion monorepo:
  `cd /Users/dahai/fusion && source .venv/bin/activate`.
- fusion-gateway on :11432 (default) or fusion-mlx directly on :11434, with a
  model loaded. `FUSION_MLX_API_KEY` is read from `~/.fusion-mlx/settings.json`
  (`auth.api_key`) if not exported.

- Python 3.12（monorepo 共享 `.venv`）；需要 fusion-gateway（:11432）或
  fusion-mlx（:11434）且已加载模型；网关 Key 缺省自动读 `~/.fusion-mlx/settings.json`。

## Install (安装)

```bash
cd /Users/dahai/fusion/fusion-health
pip install -e ".[all]"        # api + tui + test extras
```

## Start the service (启动服务)

```bash
./start.sh start     # uvicorn on http://127.0.0.1:11469, PID file .fusion-health.pid
./start.sh status    # "running (pid N, port 11469)" / "stopped"
./start.sh stop      # SIGTERM, SIGKILL after 5s
./start.sh restart
```

Persistent secrets (API key, `FUSION_HEALTH_AUDIT_HMAC_KEY`) can live in
`$HOME/.fusion-health/env` (override with `FUSION_HEALTH_ENV_FILE`); start.sh
sources it before launch.

持久密钥可放在 `~/.fusion-health/env`，start.sh 启动前自动 source。

## Verify (验证)

```bash
curl http://127.0.0.1:11469/api/v1/health
```

## First calls (第一次调用)

```bash
# clinical summary from a note file (CLI)
fusion-health ehr summary --input=./note.txt --output=./summary.json

# same via REST
curl -X POST http://127.0.0.1:11469/api/v1/ehr/summary \
  -H "Content-Type: application/json" \
  -d '{"clinical_notes": "Patient with hypertension, BP 160/95 ..."}'

# ICD-10 suggestions
fusion-health code icd10 --input=./note.txt
```

With `FUSION_HEALTH_API_KEY` set, REST clients add `X-API-Key: <key>`; when
unset, `/api/*` accepts only loopback requests.

设置 `FUSION_HEALTH_API_KEY` 后需带 `X-API-Key` 头；未设置时仅接受回环请求。

## What you no longer have to do (你不再需要做什么)

- You do not need to wire an OpenAI-compatible client yourself — `LLMGateway`
  targets fusion-gateway by default and falls back to reading the gateway key
  from `~/.fusion-mlx/settings.json`. Limitation: direct-mlx mode additionally
  needs `FUSION_HEALTH_MLX_ROUTE=chat` so the `X-Fusion-Route` header is sent.
- You do not need a separate template store — `template init` writes the 3
  built-in Jinja2 templates into a directory you control.

- 无需自写 LLM 客户端：默认指向 fusion-gateway，Key 自动兜底；直连 mlx 需加
  `FUSION_HEALTH_MLX_ROUTE=chat`。
- 无需单独维护模板库：`template init` 可导出 3 个内置 Jinja2 模板。

## Next steps (下一步)

- `docs/api-reference.md` — endpoint + client catalog
- `docs/config-reference.md` — every `FUSION_HEALTH_*` variable
- `docs/troubleshooting.md` — common failures and fixes
- `COMPLIANCE.md` / `REGULATORY.md` / `DATA_SOURCES.md` — governance posture
