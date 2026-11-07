---
doc_id: fusion-health/guide
product: fusion-health
class: app
entry: service
doc_type: guide
title: { zh: "PRD 与验收计划", en: "PRD and Acceptance Plan" }
audience: engineer
status: draft
version: 1.2.6
updated: 2026-11-07
owner: @dahai
source_of_truth:
  - fusion-health-prd-ar-plan.md
---

# Fusion-Health PRD · 架构方案 · 执行计划

> 版本：v1.0 | 日期：2026-07-28
> 基于 claude-health-insight.md 对标洞察，结合 Fusion 生态约束

---

## 一、产品定位与边界

### 1.1 产品定位

**Fusion-Health**：面向中国基层医疗场景的本地 AI 医疗辅助平台，运行在 Apple Silicon + fusion-mlx 上，数据零出境、零费用、零依赖。

**不做**：Claude Health 的本地复刻版。不追求美国企业级医疗平台的功能覆盖，而是聚焦 Claude Health 做不了的事。

### 1.2 核心差异化价值

| 维度 | Fusion-Health | Claude Health |
|------|--------------|--------------|
| 目标市场 | 中国基层/个人 | 美国大型医疗体系 |
| 核心价值 | 本地隐私优先 | 企业级 AI 平台 |
| 竞争壁垒 | 离线+中文+免费+PIPL合规 | 连接器生态+HIPAA合规 |
| 中国医保编码 | ✅ ICD-10-CN/手术操作编码 | ❌ |
| 中医辅助 | ✅ 证候辨识/方剂推荐 | ❌ |
| 断网可用 | ✅ | ❌ |

### 1.3 Fusion 生态边界定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fusion 生态 · 职责边界                         │
├─────────────┬───────────────────────────────────────────────────┤
│  项目        │  职责                                             │
├─────────────┼───────────────────────────────────────────────────┤
│ fusion-mlx  │  模型推理服务（HTTP API），不碰业务逻辑              │
│             │  边界：fusion-health 只调用 /v1/chat/completions   │
│             │  需求：无（当前 API 已满足）                        │
├─────────────┼───────────────────────────────────────────────────┤
│ fusion-code │  终端 AI 编码代理，不碰医疗业务                     │
│             │  边界：fusion-health 不依赖 fusion-code            │
│             │  需求：无                                          │
├─────────────┼───────────────────────────────────────────────────┤
│ fusion-agent│  Agent 编排平台 + 工具注册 + Agent 市场分发         │
│  -studio    │  边界：fusion-health 注册为 agent-studio 的        │
│             │  Health Agent Plugin（.fusion-agent 包）           │
│             │  需求：提交 issue 请求 Plugin 注册标准化接口         │
├─────────────┼───────────────────────────────────────────────────┤
│ fusion-     │  Artifact 管理（版本/注入/导出/同步）                │
│ artifacts   │  边界：fusion-health 生成的报告/文档通过             │
│  -engine    │  artifacts-engine 管理生命周期                     │
│             │  需求：提交 issue 请求 medical artifact kind        │
├─────────────┼───────────────────────────────────────────────────┤
│ fusion-     │  本项目 · 医疗业务逻辑层                           │
│ health      │  边界：只改自己的代码，不侵入上述项目                 │
│             │  通过 HTTP/JSON-RPC/Plugin 协议与上游交互           │
└─────────────┴───────────────────────────────────────────────────┘
```

**原则**：
- fusion-health 只改自己的代码
- 对其他项目有需求 → 提 issue + PR，不直接改
- 交互协议：HTTP REST / JSON-RPC 2.0 / Plugin 接口

---

## 二、PRD — 产品需求定义

### 2.1 目标用户画像

| 用户 | 场景 | 核心诉求 |
|------|------|---------|
| 社区诊所医生 | 门诊量 50-100/天，写病历占 40% 时间 | 快速生成结构化病历，节省书写时间 |
| 乡镇卫生院 | 无 EHR 系统，纸质病历为主 | 低成本电子化病历工具 |
| 中医院医生 | 中医辨证论治 | 证候辨识辅助、方剂推荐 |
| 医保审核员 | ICD-10-CN 编码核对 | AI 辅助编码 + 规则校验 |
| 个人健康管理者 | 自身/家人健康数据 | 离线健康数据分析、就医准备 |

### 2.2 功能模块定义（按优先级排序）

#### Phase 1 — 可信基础（P0，解决根本性缺陷）

##### M1: Pydantic 模型层 + 配置系统

**需求**：
- 所有 AI 输出必须经过 Pydantic schema 校验，校验失败返回明确错误
- 模型名、API URL、温度、max_tokens 全部可通过配置文件/环境变量设置
- 消除硬编码 `qwen3.5-9b`，支持通过 fusion-mlx 切换任意模型

**验收标准**：
- `pip install fusion-health` 后 `fusion-health ehr summary --input=test.txt` 正常工作
- 设置 `FUSION_HEALTH_MODEL=qwen3.6-27b` 后使用指定模型
- AI 返回非 JSON 内容时，不崩溃，返回 `{"error": "schema_validation_failed", "raw": "..."}`

##### M2: 医学编码可信层

**需求**：
- 内嵌 ICD-10-CN 编码数据（公开可获取的 CMS/国家卫健委标准）
- AI 建议编码后，用本地数据库交叉验证，标注"已验证"/"AI推测"
- 中国手术操作编码（ICD-9-CM-3 中国版）同理
- `confidence` 字段改为"验证状态"枚举：`verified` / `ai_suggested` / `unverified`

**验收标准**：
- `fusion-health code icd10 --input="高血压"` 返回的编码含 `status: "verified"`
- AI 幻觉出的编码标记为 `status: "ai_suggested"`
- 编码数据文件可独立更新（不影响代码）

##### M3: 文献检索真实数据源

**需求**：
- 接入 PubMed E-utilities API（免费，REST，无需 key）
- 接入 Semantic Scholar API（免费，REST，无需 key）
- 检索结果来自真实论文数据库，含 DOI/PMID
- AI 只做结果摘要，不再"生成"论文
- 离线模式：提供本地文献索引缓存

**验收标准**：
- `fusion-health literature "diabetes treatment"` 返回的每篇论文有真实 DOI
- DOI 可在 https://pubmed.ncbi.nlm.nih.gov/ 验证
- 断网时使用缓存，明确提示"离线模式，结果可能不完整"

##### M4: 合规规则引擎

**需求**：
- 实现基于规则的合规检查（非 AI 自由判断）
- HIPAA 规则清单（供参考）
- 中国《个人信息保护法》数据脱敏检查规则
- 中国《病历书写基本规范》文档完整性检查规则
- AI 只做语义理解辅助，规则做硬校验
- 输出含 `rule_id` + `rule_description` + `pass/fail` + `ai_analysis`

**验收标准**：
- 缺少主诉的病历 → `rule_id: "CN-MR-001", status: "fail"`
- 含身份证号的病历 → `rule_id: "PIPL-001", status: "fail", detail: "检测到身份证号"`
- 规则可独立增删改（YAML/JSON 配置文件）

#### Phase 2 — 中国特色能力（P1，差异化竞争）

##### M5: 中国医保编码体系

**需求**：
- ICD-10-CN（国家卫健委版，非 WHO 原版）编码数据库
- 中国手术操作分类代码（ICD-9-CM-3 中国版）
- DRG/DIP 分组辅助建议
- 医保目录匹配（甲类/乙类/自费）
- 中国医保结算单审核

**验收标准**：
- `fusion-health code icd10-cn --input="2型糖尿病"` 返回 ICD-10-CN 编码
- `fusion-health code drg --input="急性阑尾炎切除术"` 返回 DRG 分组建议
- 编码库数据可独立更新

##### M6: 中医辅助模块

**需求**：
- 证候辨识：基于症状描述推荐中医证型
- 方剂推荐：基于证型推荐经典方剂
- 中药配伍禁忌检查
- 中西医结合病历模板

**验收标准**：
- `fusion-health tcm syndrome --input="头痛眩晕，面红目赤"` 推荐肝阳上亢证
- 配伍禁忌提示（如十八反、十九畏）
- 输出含中医标准术语（参照国标 GB/T 16751）

##### M7: FHIR R4 资源映射

**需求**：
- 核心资源映射：Patient, Observation, Condition, Procedure, MedicationRequest
- EHR 输出可选 FHIR JSON 格式
- 生命体征自动映射为 Observation 资源
- 诊断映射为 Condition 资源

**验收标准**：
- `fusion-health ehr vitals --input=notes.txt --format=fhir` 返回 FHIR Observation Bundle
- FHIR JSON 通过 https://hl7.org/fhir/validation.html 校验

#### Phase 3 — 平台集成（P1，融入 Fusion 生态）

##### M8: fusion-agent-studio Health Plugin

**需求**：
- 将 fusion-health 的核心能力封装为 fusion-agent-studio 的 Tool Plugin
- 注册到 `~/.fusion-agent-studio/plugins/` 目录
- 作为 Agent Graph 中的 Tool Node 使用
- 支持 agent-studio 的 JSON-RPC 调用

**验收标准**：
- 在 agent-studio 中创建包含 `ehr_summary` tool 的 agent graph
- 执行该 graph 能得到临床摘要结果
- 不修改 agent-studio 任何代码

**向上游提交**：
- Issue: 请求 Tool Plugin 标准化接口文档
- PR: 提供 health-tools plugin 示例

##### M9: fusion-artifacts-engine 医疗文档管理

**需求**：
- 通过 artifacts-engine JSON-RPC API 管理医疗文档生命周期
- 出院小结、合规报告等作为 artifact 存储
- 版本追踪 + 导出为 PDF/Word
- 新增 `medical` artifact kind

**验收标准**：
- 生成出院小结后自动创建 artifact
- 可查询历史版本、导出文件
- 不修改 artifacts-engine 代码（先通过现有 kind=`document` 适配）

**向上游提交**：
- Issue: 请求新增 `medical` artifact kind
- PR: 提供 medical kind 的 schema 定义

##### M10: FastAPI 服务层

**需求**：
- 提供 REST API，供 Web UI / 移动端 / agent-studio 调用
- WebSocket 支持 SSE 流式输出
- 鉴权：API Key（本地场景简单即可）

**验收标准**：
- `POST /api/v1/ehr/summary` 返回临床摘要
- `GET /api/v1/health` 返回服务状态
- agent-studio 可通过 HTTP 调用

#### Phase 4 — 体验提升（P2）

##### M11: 交互式 TUI

**需求**：
- 替代纯 argparse CLI
- 提供菜单式交互、实时流式输出
- 参考 fusion-code 的 Ink TUI 模式

##### M12: 多轮对话

**需求**：
- 医疗场景天然需要追问和确认
- 实现 conversation memory（短期 + 长期）
- 通过 fusion-mlx 的多轮 messages 传递

##### M13: 批量处理

**需求**：
- 批量处理病历文件目录
- 并发控制（不压垮 fusion-mlx）
- 进度显示 + 结果汇总

##### M14: 输出模板系统

**需求**：
- 出院小结、理赔报告、合规报告等按模板生成
- 支持自定义 Jinja2 模板
- 模板目录 `~/.fusion-health/templates/`

---

## 三、技术架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户接入层                                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │   CLI    │  │  FastAPI │  │ agent-studio  │  │   artifacts   │  │
│  │(argparse)│  │  REST/WS │  │   Plugin      │  │   engine      │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  └──────┬────────┘  │
│       │              │               │                   │          │
└───────┼──────────────┼───────────────┼───────────────────┼──────────┘
        │              │               │                   │
┌───────▼──────────────▼───────────────▼───────────────────▼──────────┐
│                    fusion-health 核心层                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    配置层 (config.py)                        │    │
│  │  FUSION_HEALTH_MODEL / FUSION_HEALTH_MLX_URL / templates    │    │
│  └─────────────────────────┬───────────────────────────────────┘    │
│                            │                                        │
│  ┌─────────────────────────▼───────────────────────────────────┐    │
│  │                  推理网关 (llm_gateway.py)                    │    │
│  │  统一 HTTP 调用 → fusion-mlx /v1/chat/completions           │    │
│  │  重试 / 超时 / 模型路由 / 流式输出                            │    │
│  └─────────────────────────┬───────────────────────────────────┘    │
│                            │                                        │
│  ┌──────────┬──────────┬───┴───┬──────────┬──────────┬──────────┐  │
│  │   EHR    │  Insurance│Literature│Compliance│  TCM    │  FHIR   │  │
│  │ Processor│  Coder   │Retriever │ Checker  │Assistant │ Mapper  │  │
│  │          │          │          │          │         │         │  │
│  │·summary  │·icd10-cn │·pubmed   │·rule_    │·syndrome│·patient │  │
│  │·discharge│·cpt-cn   │·semantic │  engine  │·formula │·observ  │  │
│  │·vitals   │·drg/dip  │·scholar  │·pipl_    │·contra_ │·condit  │  │
│  │·fhir_out │·audit    │·local_   │  check   │  indica │·proced  │  │
│  │          │          │  cache   │·hipaa_   │         │·medicat │  │
│  │          │          │          │  ref     │         │         │  │
│  └────┬─────┴────┬─────┴────┬────┴────┬─────┴────┬────┴────┬────┘  │
│       │          │          │         │          │         │        │
│  ┌────▼──────────▼──────────▼─────────▼──────────▼─────────▼────┐  │
│  │                   数据层 (data/)                               │  │
│  │                                                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │  │
│  │  │ ICD-10-CN   │ │ 手术操作编码  │ │ 合规规则库   │            │  │
│  │  │ 编码数据库   │ │ ICD-9-CM-3  │ │ (YAML)      │            │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │  │
│  │  │ 中医方剂库   │ │ 配伍禁忌库   │ │ 文献缓存     │            │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                  Pydantic 模型层 (schemas/)                    │  │
│  │  ClinicalSummary / ICDCodeResult / LiteratureResult / ...    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                 Artifact 集成层 (artifact_client.py)           │  │
│  │  JSON-RPC → fusion-artifacts-engine (localhost:11451)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP /v1/chat/completions
┌───────────────────────────────▼─────────────────────────────────────┐
│                    fusion-mlx（模型推理服务）                         │
│                    localhost:11434                                   │
│                    Apple Silicon MLX Runtime                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
fusion_health/
├── __init__.py
├── config.py                    # 配置管理（环境变量 + YAML）
├── llm_gateway.py               # 统一推理网关（替代每个类单独 httpx）
├── schemas/                     # Pydantic 输出模型
│   ├── __init__.py
│   ├── ehr.py                   # ClinicalSummary, DischargeSummary, VitalsResult
│   ├── insurance.py             # ICDCodeResult, CPTCodeResult, ClaimAuditResult
│   ├── literature.py            # LiteratureSearchResult, EvidenceSummary
│   ├── compliance.py            # ComplianceAuditResult, RegulatoryCheckResult
│   ├── tcm.py                   # SyndromeResult, FormulaResult, ContraindicationResult
│   └── fhir.py                  # FHIRBundle, FHIRObservation, FHIRCondition
├── ehr/
│   ├── __init__.py
│   └── processor.py             # EHRProcessor（重构版）
├── insurance/
│   ├── __init__.py
│   ├── coder.py                 # InsuranceCoder（重构版）
│   └── icd_validator.py         # ICD-10-CN / CPT 编码验证器
├── literature/
│   ├── __init__.py
│   ├── retriever.py             # LiteratureRetriever（重构版，接 PubMed）
│   ├── pubmed_client.py         # PubMed E-utilities API 客户端
│   └── semantic_scholar.py      # Semantic Scholar API 客户端
├── compliance/
│   ├── __init__.py
│   ├── checker.py               # ComplianceChecker（重构版，规则引擎）
│   ├── rule_engine.py           # 规则引擎核心
│   └── rules/                   # 合规规则 YAML 文件
│       ├── pipl.yaml            # 中国个人信息保护法规则
│       ├── medical_record.yaml  # 病历书写规范规则
│       └── hipaa_ref.yaml       # HIPAA 参考规则（非认证）
├── tcm/                         # 中医辅助模块
│   ├── __init__.py
│   ├── assistant.py             # TCMAssistant
│   ├── formula_db.py            # 方剂数据库
│   └── contraindication.py      # 配伍禁忌检查
├── fhir/                        # FHIR R4 映射
│   ├── __init__.py
│   └── mapper.py                # FHIRMapper
├── data/                        # 静态数据文件
│   ├── icd10_cn/                # ICD-10-CN 编码数据库
│   ├── icd9_cm3_cn/             # 手术操作编码数据库
│   ├── tcm_formulas/            # 中医方剂数据
│   └── contraindications/       # 配伍禁忌数据
├── artifact_client.py           # fusion-artifacts-engine 客户端
├── api/                         # FastAPI 服务层
│   ├── __init__.py
│   ├── app.py                   # FastAPI app
│   ├── routes/
│   │   ├── ehr.py
│   │   ├── insurance.py
│   │   ├── literature.py
│   │   ├── compliance.py
│   │   ├── tcm.py
│   │   └── health.py            # 健康检查
│   └── middleware.py
├── cli/                         # CLI 入口（重构版）
│   └── __init__.py
└── plugins/                     # fusion-agent-studio 插件
    └── health_tools.py          # BaseTool 子类，注册到 agent-studio
```

### 3.3 核心模块设计

#### 3.3.1 配置层 (config.py)

```python
import os
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class HealthConfig:
    mlx_url: str = "http://localhost:11434/v1"
    model: str = "qwen3.5-9b"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: float = 60.0
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    rules_dir: Path = field(default_factory=lambda: Path(__file__).parent / "compliance" / "rules")
    templates_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "templates")
    artifacts_url: str = "http://localhost:11451"
    literature_cache_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "lit_cache")
    pubmed_enabled: bool = True
    semantic_scholar_enabled: bool = True

    @classmethod
    def from_env(cls) -> "HealthConfig":
        cfg = cls()
        cfg.mlx_url = os.getenv("FUSION_HEALTH_MLX_URL", cfg.mlx_url)
        cfg.model = os.getenv("FUSION_HEALTH_MODEL", cfg.model)
        cfg.temperature = float(os.getenv("FUSION_HEALTH_TEMPERATURE", cfg.temperature))
        cfg.max_tokens = int(os.getenv("FUSION_HEALTH_MAX_TOKENS", cfg.max_tokens))
        cfg.timeout = float(os.getenv("FUSION_HEALTH_TIMEOUT", cfg.timeout))
        cfg.artifacts_url = os.getenv("FUSION_ARTIFACTS_URL", cfg.artifacts_url)
        yaml_path = Path.home() / ".fusion-health" / "config.yaml"
        if yaml_path.exists():
            with open(yaml_path) as f:
                overrides = yaml.safe_load(f) or {}
            for k, v in overrides.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg
```

#### 3.3.2 推理网关 (llm_gateway.py)

替代当前每个类各自创建 httpx.AsyncClient 的模式，统一管理：

```python
import json
import logging
from typing import Any
import httpx
from .config import HealthConfig
from .schemas.base import LLMResult

logger = logging.getLogger(__name__)

class LLMGateway:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_schema: type | None = None,
    ) -> LLMResult:
        model = model or self.config.model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.config.mlx_url}/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info("LLM response: model=%s, len=%d", model, len(content))

            if response_schema:
                return self._parse_structured(content, response_schema)
            return LLMResult(content=content, raw=content, model=model)

        except httpx.HTTPStatusError as e:
            logger.error("LLM HTTP error: %s %s", e.response.status_code, e.response.text[:200])
            return LLMResult(content="", error=f"HTTP {e.response.status_code}", model=model)
        except Exception as e:
            logger.error("LLM error: %s", e)
            return LLMResult(content="", error=str(e), model=model)

    def _parse_structured(self, content: str, schema: type) -> LLMResult:
        try:
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(text)
            validated = schema.model_validate(data)
            return LLMResult(content=content, parsed=validated, model=self.config.model)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Schema validation failed: %s, raw: %s", e, content[:200])
            return LLMResult(
                content=content,
                error=f"schema_validation_failed: {e}",
                raw=content,
                model=self.config.model,
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

#### 3.3.3 Pydantic Schema 基础

```python
from pydantic import BaseModel, Field
from typing import Any
from enum import Enum

class VerificationStatus(str, Enum):
    verified = "verified"
    ai_suggested = "ai_suggested"
    unverified = "unverified"

class LLMResult(BaseModel):
    content: str = ""
    parsed: Any = None
    error: str = ""
    raw: str = ""
    model: str = ""

class ClinicalSummary(BaseModel):
    chief_complaint: str = ""
    history: str = ""
    examination_findings: str = ""
    diagnosis: str = ""
    treatment_plan: str = ""
    confidence_notes: str = ""

class ICDCodeItem(BaseModel):
    code: str
    description: str
    status: VerificationStatus = VerificationStatus.ai_suggested
    source: str = "ai"

class ICDCodeResult(BaseModel):
    codes: list[ICDCodeItem] = []
    error: str = ""

class LiteratureItem(BaseModel):
    title: str
    authors: str = ""
    journal: str = ""
    year: int = 0
    doi: str = ""
    pmid: str = ""
    source: str = "pubmed"
    summary: str = ""

class LiteratureSearchResult(BaseModel):
    results: list[LiteratureItem] = []
    total_found: int = 0
    offline: bool = False
    error: str = ""

class ComplianceRuleResult(BaseModel):
    rule_id: str
    rule_description: str
    status: str  # pass / fail / warning
    detail: str = ""
    ai_analysis: str = ""

class ComplianceAuditResult(BaseModel):
    overall_compliant: bool = False
    rules_checked: list[ComplianceRuleResult] = []
    error: str = ""
```

#### 3.3.4 ICD 编码验证器 (insurance/icd_validator.py)

```python
import csv
import logging
from pathlib import Path
from typing import Any
from ..config import HealthConfig

logger = logging.getLogger(__name__)

class ICDValidator:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._icd10_db: dict[str, dict] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        db_path = self.config.data_dir / "icd10_cn" / "icd10_cn.tsv"
        if not db_path.exists():
            logger.warning("ICD-10-CN database not found at %s", db_path)
            return
        with open(db_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                self._icd10_db[row["code"]] = row
        self._loaded = True
        logger.info("Loaded %d ICD-10-CN codes", len(self._icd10_db))

    def validate(self, code: str) -> dict[str, Any]:
        self._load()
        entry = self._icd10_db.get(code)
        if entry:
            return {"valid": True, "description": entry.get("description", ""), "category": entry.get("category", "")}
        return {"valid": False, "description": "", "category": ""}

    def search(self, keyword: str, limit: int = 10) -> list[dict]:
        self._load()
        results = []
        keyword_lower = keyword.lower()
        for code, entry in self._icd10_db.items():
            desc = entry.get("description", "").lower()
            if keyword_lower in desc or keyword_lower in code:
                results.append({"code": code, **entry})
                if len(results) >= limit:
                    break
        return results
```

#### 3.3.5 合规规则引擎 (compliance/rule_engine.py)

```python
import logging
import re
from pathlib import Path
from typing import Any
import yaml

logger = logging.getLogger(__name__)

class RuleEngine:
    def __init__(self, rules_dir: Path | None = None):
        self.rules_dir = rules_dir or Path(__file__).parent / "rules"
        self._rules: list[dict] = []

    def load_rules(self):
        self._rules = []
        for yaml_file in sorted(self.rules_dir.glob("*.yaml")):
            with open(yaml_file, encoding="utf-8") as f:
                rule_set = yaml.safe_load(f) or {}
            for rule in rule_set.get("rules", []):
                self._rules.append(rule)
        logger.info("Loaded %d compliance rules from %s", len(self._rules), self.rules_dir)

    def check(self, text: str) -> list[dict[str, Any]]:
        if not self._rules:
            self.load_rules()
        results = []
        for rule in self._rules:
            result = self._evaluate_rule(rule, text)
            results.append(result)
        return results

    def _evaluate_rule(self, rule: dict, text: str) -> dict[str, Any]:
        rule_id = rule["id"]
        rule_type = rule.get("type", "keyword")

        if rule_type == "keyword":
            keywords = rule.get("keywords", [])
            found = [kw for kw in keywords if kw in text]
            status = "fail" if found else "pass"
            detail = f"Found keywords: {found}" if found else ""
        elif rule_type == "regex":
            pattern = rule.get("pattern", "")
            match = re.search(pattern, text)
            status = "fail" if match else "pass"
            detail = f"Matched: {match.group()}" if match else ""
        elif rule_type == "required":
            required = rule.get("fields", [])
            missing = [f for f in required if f not in text]
            status = "fail" if missing else "pass"
            detail = f"Missing fields: {missing}" if missing else ""
        else:
            status = "warning"
            detail = f"Unknown rule type: {rule_type}"

        return {
            "rule_id": rule_id,
            "rule_description": rule.get("description", ""),
            "status": status,
            "detail": detail,
            "severity": rule.get("severity", "info"),
        }
```

合规规则 YAML 示例 (`compliance/rules/pipl.yaml`)：

```yaml
name: "中国个人信息保护法合规检查"
version: "1.0"
rules:
  - id: "PIPL-001"
    description: "检测身份证号泄露"
    type: "regex"
    pattern: "\\d{17}[\\dXx]"
    severity: "critical"
  - id: "PIPL-002"
    description: "检测手机号泄露"
    type: "regex"
    pattern: "1[3-9]\\d{9}"
    severity: "critical"
  - id: "PIPL-003"
    description: "检测银行卡号泄露"
    type: "regex"
    pattern: "\\d{16,19}"
    severity: "high"
```

```yaml
name: "病历书写基本规范检查"
version: "1.0"
rules:
  - id: "CN-MR-001"
    description: "病历必须包含主诉"
    type: "required"
    fields: ["主诉", "chief complaint"]
    severity: "critical"
  - id: "CN-MR-002"
    description: "病历必须包含现病史"
    type: "required"
    fields: ["现病史", "present illness"]
    severity: "high"
  - id: "CN-MR-003"
    description: "病历必须包含体格检查"
    type: "required"
    fields: ["体格检查", "体检", "physical examination"]
    severity: "high"
```

#### 3.3.6 PubMed 客户端 (literature/pubmed_client.py)

```python
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

class PubMedClient:
    async def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            esearch_resp = await client.get(f"{PUBMED_BASE}/esearch.fcgi", params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
            })
            esearch_resp.raise_for_status()
            id_list = esearch_resp.json().get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return []

            esummary_resp = await client.get(f"{PUBMED_BASE}/esummary.fcgi", params={
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            })
            esummary_resp.raise_for_status()
            summaries = esummary_resp.json().get("result", {})

        results = []
        for pmid in id_list:
            info = summaries.get(pmid, {})
            results.append({
                "title": info.get("title", ""),
                "authors": ", ".join(a.get("name", "") for a in info.get("authors", [])),
                "journal": info.get("fulljournalname", info.get("source", "")),
                "year": int(info.get("sortpubdate", "0000")[:4]) if info.get("sortpubdate") else 0,
                "doi": info.get("elocationid", ""),
                "pmid": pmid,
                "source": "pubmed",
                "summary": info.get("sorttitle", ""),
            })
        logger.info("PubMed search: query=%s, found=%d", query, len(results))
        return results
```

#### 3.3.7 Artifact 客户端 (artifact_client.py)

```python
import logging
from typing import Any
import httpx

logger = logging.getLogger(__name__)

class ArtifactClient:
    def __init__(self, base_url: str = "http://localhost:11451"):
        self.base_url = base_url

    async def create_artifact(
        self,
        session_id: str,
        name: str,
        content: str,
        artifact_type: str = "markdown",
        kind: str = "document",
        metadata: dict | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.create",
            "params": {
                "session_id": session_id,
                "name": name,
                "type": artifact_type,
                "content": content,
                "kind": kind,
                "metadata": metadata or {},
            },
            "id": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.base_url, json=payload)
                resp.raise_for_status()
                result = resp.json().get("result")
                logger.info("Artifact created: name=%s, session=%s", name, session_id)
                return result
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return None

    async def list_artifacts(self, session_id: str) -> list[dict]:
        payload = {
            "jsonrpc": "2.0",
            "method": "artifact.list",
            "params": {"session_id": session_id},
            "id": 2,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.base_url, json=payload)
                resp.raise_for_status()
                return resp.json().get("result", [])
        except Exception as e:
            logger.warning("Artifact engine unavailable: %s", e)
            return []
```

#### 3.3.8 agent-studio 插件 (plugins/health_tools.py)

```python
from typing import Any

class BaseHealthTool:
    """Health tool 基类 — 兼容 agent-studio BaseTool 协议。"""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    async def execute(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


class EHRSummaryTool(BaseHealthTool):
    name = "ehr_summary"
    description = "生成结构化临床摘要"
    parameters = {
        "type": "object",
        "properties": {
            "clinical_notes": {"type": "string", "description": "临床笔记文本"},
        },
        "required": ["clinical_notes"],
    }

    async def execute(self, clinical_notes: str, **kwargs) -> dict[str, Any]:
        from ..ehr.processor import EHRProcessor
        from ..config import HealthConfig
        config = HealthConfig.from_env()
        processor = EHRProcessor(config=config)
        return await processor.generate_summary(clinical_notes)


class ICD10CodingTool(BaseHealthTool):
    name = "icd10_cn_coding"
    description = "建议 ICD-10-CN 诊断编码（含数据库验证）"
    parameters = {
        "type": "object",
        "properties": {
            "diagnosis_text": {"type": "string", "description": "诊断文本"},
        },
        "required": ["diagnosis_text"],
    }

    async def execute(self, diagnosis_text: str, **kwargs) -> dict[str, Any]:
        from ..insurance.coder import InsuranceCoder
        from ..config import HealthConfig
        config = HealthConfig.from_env()
        coder = InsuranceCoder(config=config)
        return await coder.suggest_icd_codes(diagnosis_text)


# 插件注册表 — agent-studio 扫描此文件自动加载
HEALTH_TOOLS = [EHRSummaryTool, ICD10CodingTool]
```

---

## 四、向上游的 Issue/PR 计划

### 4.1 fusion-mlx（模型推理服务）

| # | 类型 | 标题 | 说明 |
|---|------|------|------|
| 1 | 无需求 | — | 当前 /v1/chat/completions API 完全满足需求，无需提交 |

**结论**：fusion-mlx 不需要改动。fusion-health 只做 HTTP 消费者。

### 4.2 fusion-code（AI 编码代理）

| # | 类型 | 标题 | 说明 |
|---|------|------|------|
| 1 | 无需求 | — | fusion-code 是编码工具，与医疗无交集 |

**结论**：fusion-code 不需要改动。fusion-health 不依赖 fusion-code。

### 4.3 fusion-agent-studio（Agent 编排平台）

| # | 类型 | 标题 | 说明 |
|---|------|------|------|
| 1 | Issue | 请求 Tool Plugin 标准化注册接口 | 当前 plugin_manager.py 已有 BaseTool + 自动扫描，但缺少：① 外部包注册发现机制 ② Plugin 依赖声明 ③ Plugin 健康检查 |
| 2 | PR | 提供 health-tools plugin 示例实现 | 作为标准化接口的参考实现 |

### 4.4 fusion-artifacts-engine（Artifact 管理）

| # | 类型 | 标题 | 说明 |
|---|------|------|------|
| 1 | Issue | 请求新增 `medical` artifact kind | 当前 kind 支持 app/code/document/game/tool/template，医疗文档需要专门的 kind 来区分敏感数据、添加脱敏规则 |
| 2 | PR | 提供 medical kind 的 schema 定义 | 含 phi_detected / deidentified / compliance_status 等元数据字段 |

---

## 五、执行计划

### 5.1 时间线（8 周）

```
Week 1-2: Phase 1 — 可信基础（M1-M4）
Week 3-4: Phase 2 — 中国特色能力（M5-M6）
Week 5-6: Phase 3 — 平台集成（M7-M10）
Week 7-8: Phase 4 — 体验提升（M11-M14）
```

### 5.2 详细任务分解

#### Week 1-2: Phase 1 — 可信基础

| 天 | 任务 | 产出 | 依赖 |
|----|------|------|------|
| D1 | 创建 config.py + 环境变量体系 | config.py | 无 |
| D1 | 创建 llm_gateway.py 统一推理网关 | llm_gateway.py | config.py |
| D2 | 创建 schemas/ Pydantic 模型层 | schemas/*.py | 无 |
| D2 | 重构 EHRProcessor 使用 LLMGateway + Pydantic | ehr/processor.py | llm_gateway, schemas |
| D3 | 重构 InsuranceCoder 使用 LLMGateway + Pydantic | insurance/coder.py | llm_gateway, schemas |
| D3 | 创建 icd_validator.py + ICD-10-CN 数据文件 | insurance/icd_validator.py + data/icd10_cn/ | schemas |
| D4 | 重构 LiteratureRetriever 使用 LLMGateway | literature/retriever.py | llm_gateway, schemas |
| D4 | 创建 pubmed_client.py + semantic_scholar.py | literature/*.py | schemas |
| D5 | 重构 ComplianceChecker 使用规则引擎 | compliance/checker.py + rule_engine.py | schemas |
| D5 | 编写 PIPL + 病历规范 YAML 规则文件 | compliance/rules/*.yaml | rule_engine.py |
| D6 | 集成测试：全部 4 个模块端到端验证 | tests/ | 所有模块 |
| D7 | 修复 ICD 编码验证逻辑 + AI 交叉校验 | insurance/coder.py | icd_validator |
| D8 | 文献检索离线缓存 + 断网回退 | literature/retriever.py | pubmed_client |
| D9 | 更新 CLI 适配新接口 + 修复 [project.scripts] | cli/__init__.py + pyproject.toml | 所有模块 |
| D10 | 更新 README + docs/api.md | README.md, docs/ | 所有模块 |

**Phase 1 阶段目标**：所有 AI 输出经 Pydantic 校验，ICD 编码有数据库验证，文献检索有真实数据源，合规检查有规则引擎。

#### Week 3-4: Phase 2 — 中国特色能力

| 天 | 任务 | 产出 |
|----|------|------|
| D11 | 创建 tcm/ 模块骨架 + TCMAssistant | tcm/assistant.py |
| D12 | 中医方剂数据库 + 配伍禁忌库 | data/tcm_formulas/, data/contraindications/ |
| D13 | 证候辨识功能 + 配伍禁忌检查 | tcm/assistant.py, tcm/contraindication.py |
| D14 | ICD-10-CN 完整数据加载 + 中国手术操作编码 | data/icd10_cn/, data/icd9_cm3_cn/ |
| D15 | DRG/DIP 分组辅助建议 | insurance/coder.py 新增方法 |
| D16 | 医保目录匹配 | insurance/coder.py 新增方法 |
| D17 | 中国医保结算单审核 | insurance/coder.py 新增方法 |
| D18 | TCM + 医保模块测试 | tests/test_tcm.py, tests/test_insurance_cn.py |
| D19 | FHIR R4 mapper 核心资源 | fhir/mapper.py |
| D20 | FHIR 输出格式支持 | ehr/processor.py 新增 format=fhir 选项 |

**Phase 2 阶段目标**：中医辅助可用，中国医保编码体系可用，FHIR 输出可用。

#### Week 5-6: Phase 3 — 平台集成

| 天 | 任务 | 产出 |
|----|------|------|
| D21 | 创建 artifact_client.py | artifact_client.py |
| D22 | 集成 artifacts-engine 到核心流程 | ehr/insurance/literature/compliance 模块 |
| D23 | 创建 agent-studio health_tools 插件 | plugins/health_tools.py |
| D24 | 向 agent-studio 提交 Issue + PR | GitHub issue + PR |
| D25 | 向 artifacts-engine 提交 Issue + PR | GitHub issue + PR |
| D26 | 创建 FastAPI 服务层骨架 | api/app.py, api/routes/ |
| D27 | EHR + Insurance + Literature REST 端点 | api/routes/*.py |
| D28 | Compliance + TCM REST 端点 | api/routes/*.py |
| D29 | WebSocket SSE 流式输出 | api/routes/ + middleware |
| D30 | API 集成测试 | tests/test_api.py |

**Phase 3 阶段目标**：FastAPI 服务可用，agent-studio 插件可用，artifacts 管理可用。

#### Week 7-8: Phase 4 — 体验提升

| 天 | 任务 | 产出 |
|----|------|------|
| D31 | TUI 骨架（textual/rich） | cli/tui.py |
| D32 | TUI 菜单 + 流式输出 | cli/tui.py |
| D33 | 多轮对话会话管理 | llm_gateway.py 扩展 |
| D34 | 对话记忆（短期 + 长期） | config.py + 新模块 |
| D35 | 批量文件处理 | cli/ 新增 batch 子命令 |
| D36 | 输出模板系统（Jinja2） | templates/ |
| D37 | 模板目录 + 默认模板 | ~/.fusion-health/templates/ |
| D38 | 完整 E2E 测试 + 性能测试 | tests/ |
| D39 | 文档更新（README + API docs + 使用指南） | docs/ |
| D40 | v1.0.0 发布准备（changelog + tag） | release |

**Phase 4 阶段目标**：TUI 可用，多轮对话可用，批量处理可用，v1.0.0 发布。

### 5.3 依赖关系图

```
M1 (Pydantic+Config) ──┬──> M2 (编码可信) ──> M5 (中国医保)
                       ├──> M3 (文献真实) ──> (无后续依赖)
                       ├──> M4 (合规规则) ──> (无后续依赖)
                       └──> M7 (FHIR映射)
                                              │
M8 (agent-studio Plugin) <── M1 ──────────────┘
M9 (artifacts 集成) <─────── M1 ──────────────┘
M10 (FastAPI) <───────────── M1 + M8 ─────────┘
M6 (中医辅助) <───────────── M1 ──────────────┘
M11 (TUI) <───────────────── M10 ─────────────┘
M12 (多轮对话) <───────────── M1 + M10 ────────┘
M13 (批量处理) <───────────── M10 ─────────────┘
M14 (模板系统) <───────────── M10 ─────────────┘
```

### 5.4 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| ICD-10-CN 数据获取困难 | 中 | 高 | 先用 WHO ICD-10 + 中国扩展映射，数据不全时降级为 AI 建议 |
| PubMed API 在中国访问受限 | 高 | 中 | 实现离线缓存 + 中国医学文献数据库备选（万方/知网 API 需授权） |
| agent-studio Plugin 接口变更 | 低 | 中 | 遵循现有 BaseTool 协议，不过度依赖未稳定接口 |
| qwen3.5-9b 医疗推理能力不足 | 中 | 高 | 配置支持切换大模型（27B/72B），性能换质量 |
| 合规规则不完整 | 中 | 中 | 规则引擎支持 YAML 热加载，规则可持续增补 |

---

## 六、成功指标

| 指标 | Phase 1 目标 | v1.0 目标 |
|------|-------------|-----------|
| ICD 编码验证覆盖率 | ≥ 80% ICD-10-CN 常用编码 | ≥ 95% |
| 文献检索真实来源占比 | ≥ 90% | 100%（离线模式除外） |
| 合规规则覆盖 | PIPL + 病历规范 ≥ 20 条 | ≥ 50 条 |
| Pydantic 校验通过率 | ≥ 95%（正常输入） | ≥ 99% |
| 端到端延迟（临床摘要） | ≤ 30s（qwen3.5-9b） | ≤ 15s（更大模型） |
| 测试覆盖率 | ≥ 80% | ≥ 90% |
| 中国医保编码支持 | ICD-10-CN | ICD-10-CN + 手术编码 + DRG |
| 中医模块 | 无 | 证候辨识 + 方剂 + 禁忌 |

---

## 七、附录

### A. 环境变量一览

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FUSION_HEALTH_MLX_URL` | `http://localhost:11434/v1` | fusion-mlx API 地址 |
| `FUSION_HEALTH_MODEL` | `qwen3.5-9b` | 默认模型名 |
| `FUSION_HEALTH_TEMPERATURE` | `0.1` | 默认温度 |
| `FUSION_HEALTH_MAX_TOKENS` | `2048` | 默认最大 token 数 |
| `FUSION_HEALTH_TIMEOUT` | `60.0` | HTTP 超时秒数 |
| `FUSION_ARTIFACTS_URL` | `http://localhost:11451` | artifacts-engine 地址 |
| `FUSION_HEALTH_PUBMED_ENABLED` | `1` | 是否启用 PubMed |
| `FUSION_HEALTH_OFFLINE` | `0` | 强制离线模式 |

### B. pyproject.toml 变更计划

```toml
[project]
name = "fusion-health"
version = "1.0.0"
description = "Fusion-Health — 本地 AI 医疗辅助平台，由 fusion-mlx 驱动"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
api = ["fastapi>=0.110.0", "uvicorn>=0.29.0", "websockets>=12.0"]
tui = ["textual>=0.50.0", "rich>=13.0.0"]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "httpx",
]
all = ["fusion-health[api,tui,test]"]

[project.scripts]
fusion-health = "fusion_health.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### C. ICD-10-CN 数据获取方案

数据源：国家卫健委标准 ICD-10 编码（公开可获取）

1. 国家卫健委统计信息中心发布的 ICD-10 编码标准
2. CMS ICD-10-CM 官方数据文件（https://www.cms.gov/Medicare/Coding/ICD10）作为补充
3. 数据格式：TSV 文件，字段 `code | description_cn | description_en | category`

### D. 中医数据来源

1. 《中医病证分类与代码》（GB/T 15657）— 证候编码标准
2. 《中华人民共和国药典》— 方剂组成标准
3. 十八反、十九畏 — 配伍禁忌标准

数据以 JSON/TSV 格式存储在 `data/tcm_formulas/` 和 `data/contraindications/` 目录。
