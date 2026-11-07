---
doc_id: fusion-health/config-reference
product: fusion-health
class: app
entry: service
doc_type: config-reference
title: { zh: "配置参考", en: "Configuration Reference" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - fusion_health/config.py
  - start.sh
  - README.md
---

# Configuration Reference (配置参考)

Env-driven, resolved by `fusion_health/config.py` (single-point resolution via
`fusion_core.config` since v1.2.3). start.sh reads an optional env file first:
`FUSION_HEALTH_ENV_FILE` (default `~/.fusion-health/env`).

## Service (服务)

| Variable | Default | Purpose |
|---|---|---|
| `FUSION_HEALTH_PORT` | `11469` | HTTP port (port-registry: 11469) |
| `FUSION_HEALTH_HOST` | `127.0.0.1` | Bind address; `0.0.0.0` requires an API key |
| `FUSION_HEALTH_API_KEY` | unset | When set, clients send `X-API-Key`; when unset, loopback-only |
| `FUSION_HEALTH_VENV` | `/Users/dahai/fusion/.venv` | venv used by start.sh |
| `FUSION_HEALTH_ENV_FILE` | `~/.fusion-health/env` | Optional persistent env file for secrets |
| `FUSION_HEALTH_API_PORT` | (deprecated) | Legacy name; warns and maps to `FUSION_HEALTH_PORT` |

## Engine (模型引擎)

| Variable | Default | Purpose |
|---|---|---|
| `FUSION_HEALTH_MLX_URL` | `http://localhost:11432/v1` | fusion-gateway endpoint |
| `FUSION_MLX_API_KEY` | auto from `~/.fusion-mlx/settings.json` | Gateway API key; alias `FUSION_HEALTH_MLX_API_KEY` |
| `FUSION_HEALTH_MLX_ROUTE` | unset | Set `chat` for direct-mlx mode so `X-Fusion-Route` is sent |
| `FUSION_HEALTH_MODEL` | (fusion-mlx loaded model) | Model override |
| `FUSION_HEALTH_TEMPERATURE` | (config default) | Sampling temperature |
| `FUSION_HEALTH_MAX_TOKENS` | (config default) | Max tokens per completion |
| `FUSION_HEALTH_TIMEOUT` | (config default) | HTTP timeout seconds |

## Behavior (行为)

| Variable | Default | Purpose |
|---|---|---|
| `FUSION_HEALTH_RATE_LIMIT_RPM` | unset/off | Per-minute request cap |
| `FUSION_HEALTH_SESSION_TTL` | (config default) | Chat session expiry seconds |
| `FUSION_HEALTH_PUBMED_ENABLED` | `1` | `0` disables the PubMed client |
| `FUSION_HEALTH_S2_ENABLED` | `1` | `0` disables Semantic Scholar |
| `FUSION_HEALTH_OFFLINE` | `0` | `1` forces offline behavior (no external literature calls) |
| `FUSION_ARTIFACTS_URL` | unset | fusion-artifacts-engine endpoint for artifact export |
| `FUSION_HEALTH_AUDIT_HMAC_KEY` | unset | HMAC key for the audit chain (keep in the env file, never in git) |

## Precedence (优先级)

Env var > `~/.fusion-health/env` file (sourced by start.sh) > gateway-key
auto-read from `~/.fusion-mlx/settings.json` > built-in default. Exact numeric
defaults live in `fusion_health/config.py`; this doc does not duplicate every
constant.
