# Regulatory Path — Fusion-Health

**STATUS: DRAFT — not filed. Requires NMPA consultant + legal review before any commercial use.**

Fusion-Health is clinical decision-support software (CDSS) + medical coding assist. In China, software that provides diagnosis/treatment suggestions or directly affects clinical decisions is a **医疗器械 (medical device)** regulated by **NMPA (国家药品监督管理局)**. This document maps the likely classification and path. It is guidance, not legal advice.

## Likely Device Classification

| Function | Likely Class | Basis |
|---|---|---|
| EHR summarization | Class II | Processing clinical data to produce summaries that inform decisions |
| ICD-10 / DRG / catalog coding assist | Class II | Affects billing/reimbursement; output used in claims |
| TCM syndrome + formula recommendation | **Class III risk** if it directly drives prescription | Direct treatment recommendation — highest risk |
| Literature retrieval | Not a device (information only) | No clinical decision output |
| Compliance audit | Not a device (administrative) | Documentation checking |

**Recommended scope for first filing:** EHR summarization + coding assist (Class II). Defer TCM prescription recommendation from the commercial product until Class III evidence is gathered, or restrict it to **information-only** with mandatory physician sign-off (does not auto-prescribe).

## NMPA Registration Path (Class II)

1. **Determine classification** via 《医疗器械分类目录》 + 分类界定申请 (pre-submission classification request to NMPA). ~2-3 months.
2. **Establish Quality Management System (QMS)** per YY/T 0287 (ISO 13485 adapted). Required before submission.
3. **Clinical evaluation** — one of:
   - Clinical trial (high evidence, slow)
   - Equivalence comparison to a predicate device (faster, if a comparable registered CDSS exists)
   - Literature route (limited applicability for novel AI)
4. **Product technical requirements (产品技术要求)** — performance specs, the clinical_eval.py golden-set results feed here.
5. **Registration dossier** → NMPA technical review → on-site QMS audit → certificate.
6. **Estimated timeline:** 12-18 months for Class II AI software.

## Evidence This Repo Already Produces

These artifacts support (not replace) the clinical evaluation dossier:

- `fusion_health/clinical_eval.py` — golden-set eval harness (precision/recall/F1)
- `tests/test_clinical_eval.py` — verified against live model (5/5 hit, F1=0.91 on sample set)
- `fusion-health eval` CLI — reproducible eval runs
- `DATA_SOURCES.md` — coding dataset provenance (required for coding-assist accuracy claims)
- `COMPLIANCE.md` — PHI handling, audit trail (data governance evidence)

**CRITICAL GAP:** the golden set (5 cases) is a smoke test, not clinical validation. NMPA submission requires a **clinician-verified golden set of ≥100-300 cases** covering the device's intended scope, with documented sensitivity/specificity and a clinical evaluation report signed by a qualified medical professional.

## Required Before Commercial Sale (Human Actions)

- [ ] Engage NMPA consultant / regulatory affairs firm
- [ ] Submit classification determination request (分类界定)
- [ ] Implement YY/T 0287 QMS (design controls, risk management per YY/T 0316, traceability)
- [ ] Build clinician-verified golden set (≥100 cases, documented review)
- [ ] Run clinical_eval.py against the full golden set; produce signed clinical evaluation report
- [ ] Draft 产品技术要求 (technical requirements) with measurable performance thresholds
- [ ] Compile + submit registration dossier
- [ ] Pass NMPA technical review + on-site QMS audit
- [ ] Obtain 医疗器械注册证 before any commercial sale/marketing

## Non-NMPA Markets

- **US (FDA):** CDSS may be SaMD — likely De Novo or 510(k) if predicate exists. Separate filing.
- **EU (MDR):** Class IIa/IIb CE marking under MDR, notified body required.
- **Each market requires its own filing.** Do not assume one registration covers others.

## Disclaimer in Product

Until registered, the product UI and docs MUST display:

> 本软件为医疗辅助工具，输出仅供参考，不构成诊断或治疗建议。最终临床决策须由具备资质的医师做出。本软件尚未取得医疗器械注册证书，不得用于商业销售。

See [LEGAL.md](LEGAL.md) for terms-of-use and liability framework.
