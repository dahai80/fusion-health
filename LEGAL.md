# Legal Framework — Fusion-Health

**STATUS: DRAFT TEMPLATE — requires qualified lawyer to review and finalize before use.**

This document provides templates for the legal framework a commercial healthcare AI product needs. None of this is legal advice. Engage counsel licensed in the operating jurisdiction.

## 1. Terms of Use (Template)

> **Fusion-Health 软件使用条款（模板）**
>
> **1. 性质声明.** 本软件为医疗辅助决策支持工具，所有输出（包括但不限于 ICD 编码建议、病历摘要、证候分析）仅供参考，不构成医学诊断、治疗建议或处方。本软件尚未取得医疗器械注册证书。
>
> **2. 最终决策权.** 任何临床决策必须由具备相应执业资质的医师独立作出。使用方须对软件输出进行独立专业判断，并对最终决策承担全部责任。
>
> **3. 禁止商业销售.** 在取得 NMPA 医疗器械注册证书之前，本软件不得用于商业销售或对外提供有偿服务。
>
> **4. 适用范围.** 本软件适用于本地化部署，所有数据处理在用户自有设备上完成。详见 [COMPLIANCE.md](COMPLIANCE.md)。
>
> **5. 免责.** 在适用法律允许的最大范围内，开发方不对因使用本软件产生的任何直接、间接、 incidental 或后果性损害承担责任。软件按"现状"提供，不提供任何明示或暗示的保证。

## 2. Data Processing Agreement (DPA) — PIPL Aligned

Under 《个人信息保护法》(PIPL), processing personal information (PHI is sensitive personal information) requires:

### 2.1 Legal Basis (Art. 13)
- Separate consent (单独同意) required for sensitive personal information (Art. 29)
- Healthcare is a listed sensitive category (Art. 28)

### 2.2 Required Disclosures to Data Subjects (Art. 17, 30)
- Identity and contact of processor (处理者名称 + 联系方式)
- Purpose, necessity, and consequences of processing (处理目的/必要性/后果)
- Categories of PHI processed (PHI 种类)
- Retention period (保存期限)
- Data subject rights: access, copy, correction, deletion, withdrawal of consent (查询/复制/更正/删除/撤回同意)
- Cross-border transfer — **N/A for Fusion-Health (local-first, no cross-border transfer)**

### 2.3 Security Obligations (Art. 51, 55)
- Encryption at rest: AES-256-GCM (`FUSION_HEALTH_PHI_KEY`) — **implemented**
- Access control + audit log (HMAC-signed) — **implemented** (`fusion_health/audit.py`)
- Data protection impact assessment (个人信息保护影响评估) — **template below**
- Designated person responsible for PI protection (个人信息保护负责人)

### 2.4 Retention (Art. 19, 47)
- Healthcare records: follow 《医疗机构病历管理规定》 (inpatient ≥30 years; outpatient ≥15 years) — **operator must configure retention per local rule**
- Consent withdrawal triggers deletion unless legal retention obligation applies

### 2.5 DPA Clause Template (between operator and Fusion-Health deployer)

> 数据处理者：[运营方]
> 委托处理范围：使用 Fusion-Health 软件进行病历摘要、编码辅助、合规审计
> 数据本地化：所有 PHI 在运营方自有设备处理，不传输至第三方
> 安全措施：AES-256-GCM 静态加密、HMAC 审计日志、0600 文件权限、API 密钥鉴权
> 数据主体权利响应：由运营方负责（开发方不接触 PHI）
> 子处理者：无（本地部署，无云服务依赖）

## 3. Personal Information Protection Impact Assessment (PIPIA) Template

### 3.1 Processing Purpose & Necessity
- Purpose: clinical documentation assistance, coding accuracy, compliance audit
- Necessity: LLM-assisted summarization/coding improves clinician efficiency; no less-intrusive alternative achieves same function

### 3.2 Data Categories
- Input PHI: clinical notes, patient demographics (operator-supplied)
- Derived: summaries, code suggestions (in-memory, not persisted unless operator saves sessions)
- Audit metadata: owner ID, hashes (NOT raw PHI), timestamps

### 3.3 Risk Assessment
| Risk | Likelihood | Impact | Mitigation (implemented) |
|---|---|---|---|
| Unauthorized API access | Medium | High | API key auth, localhost-only default, rate limit |
| PHI theft from disk | Low | High | AES-256-GCM encryption, 0600 perms |
| Audit log tampering | Low | High | HMAC-SHA256 signing, seq verification |
| Model leakage of PHI | Low | Medium | Local-only inference, no cloud, session TTL |
| Excessive data retention | Medium | Medium | Operator-configured retention, DR backup script |

### 3.4 Data Subject Rights Implementation
- Access/copy: operator queries saved sessions (plaintext after decrypt with key)
- Correction: operator edits session before re-save
- Deletion: operator deletes session file (audit log retained per legal obligation, contains hashes only)
- Consent withdrawal: operator stops processing + deletes per retention policy

## 4. Liability Framework

- **Software provider:** liable for defects per 《产品质量法》and contract; but medical decision liability rests with the licensed physician (Art. 1224 民法典 — medical damage liability on medical institution/personnel)
- **Deploying institution:** liable for PHI protection per PIPL + 《数据安全法》
- **Physician:** bears clinical decision responsibility — software is advisory only (reinforced by disclaimer in §1)

## 5. Required Before Commercial Use (Human Actions)

- [ ] Lawyer reviews + finalizes Terms of Use (§1)
- [ ] Lawyer drafts + finalizes DPA (§2.5) tailored to operator relationship
- [ ] Complete PIPIA (§3) with operator-specific data flows, have data protection officer sign
- [ ] Appoint 个人信息保护负责人 (data protection officer) per PIPL Art. 52
- [ ] Register with 主管部门 if required (healthcare data may trigger 等级保护 — 等保三级 for healthcare systems)
- [ ] Confirm product disclaimer displayed in UI + CLI + docs (not just this file)

## Related

- [COMPLIANCE.md](COMPLIANCE.md) — technical PHI controls + data flow
- [REGULATORY.md](REGULATORY.md) — NMPA device registration path
- [SECURITY.md](SECURITY.md) — security posture + vulnerability reporting
