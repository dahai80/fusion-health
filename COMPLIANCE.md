# PHI & Compliance Guide

Fusion-Health processes Protected Health Information (PHI): clinical notes,
discharge summaries, conversation history. This document describes the data
flow, audit controls, retention, and deployment hardening required before
operating in a regulated (PIPL / HIPAA-aligned) environment.

## Regulatory Scope

- **PIPL** (Personal Information Protection Law, CN): governs processing of
  personal information including health data. Rules encoded in
  `fusion_health/compliance/rules/pipl.yaml` (bank-card regex, consent checks).
- **HIPAA-aligned** controls (US reference model): encryption at rest/in transit,
  audit logging, minimum necessary access. Fusion-Health implements technical
  safeguards; administrative/physical safeguards remain the operator's duty.

Fusion-Health is a **local-first** system: no PHI leaves the host by default.
LLM inference runs on `localhost` (fusion-mlx / fusion-gateway). No cloud AI.

## Data Flow

```
Client ──HTTPS──> API (FastAPI, 127.0.0.1:11469)
                   │
                   ├─ APIKeyMiddleware: auth (X-API-Key, constant-time), rate-limit, owner_id
                   ├─ audit.log_access(): HMAC-signed, PHI hashed (not stored raw)
                   ├─ Domain handler (EHR/insurance/compliance/tcm/literature/chat)
                   │     └─ LLMGateway.chat() ──localhost──> fusion-mlx (port 11434/11432)
                   ├─ ConversationSession: plaintext JSON at ~/.fusion-health/conversations/
                   └─ Response
```

### Where PHI lives

| Artifact | Path | PHI content | Protection |
|---|---|---|---|
| Audit log | `~/.fusion-health/audit.log` | **hash + length only** (no raw PHI) | 0600, HMAC-SHA256 per line, seq counter |
| Conversation sessions | `~/.fusion-health/conversations/<owner>/<sid>.json` | **raw PHI** (message text) | 0600 file perms, owner-scoped subdir |
| Config | `~/.fusion-health/config.yaml` | no PHI | owner-controlled |
| LLM request/response | in-memory / localhost network | **raw PHI** in transit to local model | loopback only |

Raw PHI persists only in conversation session files. Audit logs store a
SHA-256 hash (truncated 16 hex) + length, never the plaintext.

## Audit Logging

`fusion_health/audit.py` — every API request to a PHI-touching route writes a
tamper-evident log line:

- **HMAC-SHA256** signature over the canonical JSON body (key from
  `FUSION_HEALTH_AUDIT_HMAC_KEY` or `FUSION_HEALTH_API_KEY`, else default).
- **Monotonic sequence** counter per process.
- **Fields**: `seq`, `ts` (UTC ISO), `request_id`, `owner_id`, `method`, `path`,
  `action`, `status`, `phi_input_hash`, `phi_input_len`.
- File created `0600` via `os.open`; appended atomically under a lock.
- `verify_log_line(line)` recomputes HMAC for tamper detection.

Routes covered: `ehr/*`, `insurance/*`, `compliance/*`, `tcm/*`, `chat/*`.

Disable only for non-production: `FUSION_HEALTH_AUDIT_DISABLED=1`.

### Rotation

Audit log grows unbounded. Operator must rotate (logrotate or scheduled
archive) and preserve rotated logs for the regulatory retention period.

## Retention

| Data | Default | Recommended policy |
|---|---|---|
| Audit log | indefinite (file append) | retain per PIPL/HIPAA min (e.g. 6 yr HIPAA) |
| Conversation sessions | indefinite until manual delete or session eviction (TTL) | define org TTL; auto-purge via reaper |
| Config | indefinite | no PHI |

Session eviction: `ConversationSession` reaper removes idle sessions past
`FUSION_HEALTH_SESSION_TTL` (see `api/routes/chat.py` lifespan startup).
Operators should set a TTL consistent with their retention policy and verify
`~/.fusion-health/conversations/` purge.

## Deployment Hardening Checklist

Required before production:

- [ ] **API key set**: `FUSION_HEALTH_API_KEY=<strong random>`. Without it the
      API accepts only localhost connections (default-deny remote).
- [ ] **Audit HMAC key set**: `FUSION_HEALTH_AUDIT_HMAC_KEY` (distinct from
      API key) so signatures are independently verifiable.
- [ ] **CORS allowlist**: `FUSION_HEALTH_CORS_ORIGINS` set to explicit origins
      (never `*` with credentials in production).
- [ ] **Rate limiting**: `FUSION_HEALTH_RATE_LIMIT_RPM` tuned; for multi-worker
      set `FUSION_HEALTH_RATE_LIMIT_DB` to a shared SQLite path for
      cross-worker enforcement.
- [ ] **TLS**: terminate HTTPS upstream (reverse proxy). Fusion-Health binds
      127.0.0.1; do not expose the raw port to 0.0.0.0 without TLS + key.
- [ ] **Data source = full**: run `scripts/ingest_data.py --status` and confirm
      `.data_source == full`. Sample data must not reach clinical use
      (see `DATA_SOURCES.md`).
- [ ] **File permissions**: `~/.fusion-health/` owned by service user, 0700;
      audit log + session files 0600 (enforced in code — verify on deploy).
- [ ] **Log level**: production `WARNING`+; `DEBUG` logs may include request
      metadata. `logging_config.py` defaults appropriately.
- [ ] **Session TTL**: set `FUSION_HEALTH_SESSION_TTL` to match retention policy.
- [ ] **External sources**: disable PubMed/SemanticScholar if egress is
      prohibited (`FUSION_HEALTH_PUBMED_ENABLED=0`,
      `FUSION_HEALTH_SEMANTIC_SCHOLAR_ENABLED=0`).
- [ ] **Model**: confirm `FUSION_HEALTH_MODEL` is a clinically-validated model
      and that fusion-mlx is running. CDSS outputs are decision-support, not
      autonomous decisions.

## Operator Responsibilities (not enforced by code)

Fusion-Health provides **technical safeguards**. The operator is responsible
for **administrative** and **physical** safeguards:

- Access control policy (who holds the API key / HMAC key).
- Key rotation schedule.
- Audit log review and rotation.
- Data retention enforcement + destruction procedures.
- Breach notification process.
- Clinical validation of model outputs before any diagnostic/billing use.
- Workforce training on minimum-necessary access.

Fusion-Health is a **decision-support** tool. It does not replace clinical
judgment. No output should be used as the sole basis for diagnosis, treatment,
or billing.
