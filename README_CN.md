<div align="center">

# Fusion-Health

**本地 AI 医疗辅助平台 — 由 fusion-mlx 驱动**

处理病历、生成临床摘要、建议 ICD-10/CPT 编码、搜索临床文献、检查合规——完全本地运行，数据不出设备。

[English](README.md) · [快速开始](#快速开始) · [CLI 参考](#cli-参考) · [架构](#架构) · [文档](docs/)

</div>

---

## 为什么选择 Fusion-Health？

| 特性 | Fusion-Health | Claude Health |
|------|--------------|--------------|
| **本地离线** | ✅ 100% 本地 | ❌ 仅云端 |
| **数据隐私** | ✅ 患者数据不出设备 | ❌ 数据上传海外 |
| **国内合规** | ✅ 完全合规 | ❌ 违反《个人信息保护法》 |
| **零费用** | ✅ | ❌ 企业订阅付费 |
| **病历处理** | ✅ 摘要/出院/生命体征 | ✅ |
| **ICD-10/CPT 编码** | ✅ AI 辅助编码 | ✅ |
| **文献检索** | ✅ 循证医学检索 | ✅ |
| **合规审计** | ✅ 文档合规检查 | ✅ |
| **中文医疗支持** | ✅ 原生中文 | ❌ 有限 |

**一句话：** Fusion-Health 是 Claude Health 的本地优先、隐私合规替代方案——由 fusion-mlx 在 Apple Silicon 上驱动。

---

## 快速开始

### 安装

```bash
git clone https://github.com/dahai80/fusion-health.git
cd fusion-health
pip install -e ".[test]"
```

### 处理病历

```bash
# 生成临床摘要
fusion-health ehr summary --input=clinical_notes.txt --output=summary.json

# 生成出院小结
fusion-health ehr discharge --input=admission_notes.txt --output=discharge.md

# 提取生命体征
fusion-health ehr vitals --input=progress_notes.txt
```

### 医保编码

```bash
# 建议 ICD-10 诊断编码
fusion-health code icd10 --input="高血压伴糖尿病患者"

# 建议 CPT 手术编码
fusion-health code cpt --input="普通门诊三级"

# 审计理赔申请
fusion-health code audit --input=claim_data.txt
```

### 文献检索

```bash
fusion-health literature "2型糖尿病治疗指南" --max-results=10
```

### 合规检查

```bash
fusion-health compliance audit --input=clinical_note.txt
```

---

## CLI 参考

| 命令 | 说明 |
|------|------|
| `ehr summary --input` | 生成结构化临床摘要 |
| `ehr discharge --input` | 生成出院小结 |
| `ehr vitals --input` | 提取生命体征 |
| `code icd10 --input` | 建议 ICD-10 诊断编码 |
| `code cpt --input` | 建议 CPT 手术编码 |
| `code audit --input` | 审计理赔申请 |
| `literature <query> [--max-results]` | 搜索临床文献 |
| `compliance audit --input` | 审计临床文档 |
| `compliance regulatory --input --type` | 检查法规合规性 |

---

## 与 Claude Health 对比

| 能力 | Claude Health | Fusion-Health |
|------|-------------|--------------|
| 病历摘要 | ✅ | ✅ |
| 出院小结 | ✅ | ✅ |
| 生命体征提取 | ✅ | ✅ |
| ICD-10 编码 | ✅ | ✅ |
| CPT 编码 | ✅ | ✅ |
| 理赔审计 | ✅ | ✅ |
| 文献检索 | ✅ | ✅ |
| 循证摘要 | ✅ | ✅ |
| 文档审计 | ✅ | ✅ |
| 合规检查 | ✅ | ✅ |
| **本地离线** | ❌ 仅云端 | ✅ **100% 本地** |
| **数据隐私** | ❌ 数据上传 | ✅ **数据不出设备** |
| **国内合规** | ❌ 违法 | ✅ **完全合规** |
| **零费用** | ❌ 企业订阅 | ✅ **免费** |
| **中文医疗** | ❌ 有限 | ✅ **原生** |