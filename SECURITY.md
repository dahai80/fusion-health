# Security Policy

## Reporting a Vulnerability

DO NOT open a public GitHub issue for security vulnerabilities.

Report privately to: **[REDACTED — set SECURITY_CONTACT in deployment]**

Include: affected version, repro steps, impact assessment. Acknowledge within 72h. Fix timeline target: critical 7d, high 30d, medium 90d.

## Threat Model

Fusion-Health is a **local-first** healthcare AI service. LLM inference runs on-device via fusion-mlx (localhost only, no cloud AI calls). PHI never leaves the host except to the local inference engine over loopback.

### Assets
- **PHI** (patient health information): conversation sessions, EHR summaries, clinical notes
- **Audit logs**: tamper-evident PHI access records (HMAC-signed, sha256 hashes only — never raw PHI)
- **API keys**: MLX inference key, API access key, audit HMAC key, PHI encryption key
- **Coding datasets**: ICD-10-CN / DRG / catalog reference data

### Attack Surface
1. **HTTP API** (port 11469) — primary external surface
2. **Session files** on disk — PHI at rest
3. **Audit log** file — integrity target
4. **Dependencies** — supply chain

## Security Controls

| Control | Mechanism | Config |
|---|---|---|
| API authentication | `APIKeyMiddleware` — constant-time `hmac.compare_digest`; localhost-only when no key | `FUSION_HEALTH_API_KEY` |
| CORS | Explicit origins only; `*` rejected by enterprise gate | `FUSION_HEALTH_CORS_ORIGINS` |
| Rate limiting | Token-bucket per-owner; SQLite shared backend for multi-worker | `FUSION_HEALTH_RATE_LIMIT_RPM`, `FUSION_HEALTH_RATE_LIMIT_DB` |
| PHI encryption at rest | AES-256-GCM envelope; raw 256-bit key or passphrase→PBKDF2-HMAC-SHA256 (200k iters) | `FUSION_HEALTH_PHI_KEY` |
| Audit log integrity | HMAC-SHA256 per-line signing, sequence numbers, 0600 perms | `FUSION_HEALTH_AUDIT_HMAC_KEY` |
| Session TTL | Bounded lifetime, background reaper evicts stale | `FUSION_HEALTH_SESSION_TTL` |
| Enterprise readiness gate | Startup enforcement of all production configs | `FUSION_HEALTH_ENTERPRISE`, `FUSION_HEALTH_ENTERPRISE_HARD` |
| File permissions | Session + audit files created 0600; owner-scoped | — |

## Scanning

Two automated scanners run in CI (`.github/workflows/ci.yml`):

- **Bandit** (SAST) — `bandit -r fusion_health -q`. Scans 3835 LOC. Must report **0 issues**.
- **pip-audit** (dependency CVE) — `pip-audit --desc on`. Non-zero exit on known vulnerabilities.

Reproduce locally:
```bash
source .venv/bin/activate
bandit -r fusion_health -q          # SAST — expect clean
pip-audit --desc on                 # dependency CVEs
```

## Deployment Hardening Checklist

Before commercial deployment, ALL must be set:

- [ ] `FUSION_HEALTH_ENTERPRISE=1 FUSION_HEALTH_ENTERPRISE_HARD=1` (refuse startup on any gap)
- [ ] `FUSION_HEALTH_API_KEY` set (strong random, ≥32 bytes)
- [ ] `FUSION_HEALTH_AUDIT_HMAC_KEY` set (strong random, ≥32 bytes)
- [ ] `FUSION_HEALTH_PHI_KEY` set (64-hex raw key recommended over passphrase)
- [ ] `FUSION_HEALTH_CORS_ORIGINS` set to explicit production origins (never `*`)
- [ ] `.data_source` marker = `full` (real coding datasets ingested via `scripts/ingest_data.py`)
- [ ] TLS termination in front of API (reverse proxy / load balancer)
- [ ] Audit log + session directory on backed-up volume with documented retention
- [ ] Process runs as non-root, least-privilege user
- [ ] `FUSION_HEALTH_LOG_LEVEL` ≤ INFO in production (DEBUG may log PHI fragments)

## Out of Scope (Local-First Design)

- No outbound network calls to cloud AI
- No telemetry / phone-home
- PubMed / Semantic Scholar disabled by default (`FUSION_HEALTH_OFFLINE=1`)
- LLM inference loopback-only (localhost:11432/11434)

See [COMPLIANCE.md](COMPLIANCE.md) for PHI data flow, retention, and PIPL/HIPAA alignment.
