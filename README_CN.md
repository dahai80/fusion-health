<div align="center">

# Fusion-Health

**本地 AI 医疗助手 — 由 fusion-mlx 驱动**

处理医疗记录、生成临床摘要、推荐 ICD-10/CPT 编码、检索临床文献、合规检查 — 全部本地运行，数据不离设备。

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-148-success.svg)](tests/)

[快速开始](#快速开始) · [CLI 参考](#cli-参考) · [架构](#架构) · [文档](docs/)

**[English](README.md)** | 中文

</div>

---

## 为什么选择 Fusion-Health？

| 特性 | Fusion-Health | Claude Health |
|------|--------------|--------------|
| **本地离线** | ✅ 100% 本地 | ❌ 仅云端 |
| **数据隐私** | ✅ PHI 不离设备 | ❌ 数据上传至云端 |
| **中国合规** | ✅ 完全合规 | ❌ 违反 PIPL |
| **零 API 费用** | ✅ | ❌ 企业订阅 |
| **EHR 处理** | ✅ 摘要、出院、体征 | ✅ |
| **ICD-10/CPT 编码** | ✅ AI 辅助编码 | ✅ |
| **文献检索** | ✅ 循证检索 | ✅ |
| **合规审计** | ✅ 文档审计 | ✅ |
| **中医支持** | ✅ 原生中文 | ❌ 有限 |

**一句话：** Fusion-Health 是 Claude Health 的本地优先、隐私合规替代方案 — 基于 Apple Silicon 上的 fusion-mlx 运行。

---

## 快速开始

### 前置条件

- macOS Apple Silicon (M1–M5)，Python 3.12+
- [fusion-mlx](https://github.com/dahai80/fusion-mlx) 运行在 `localhost:11434`（默认模型 `Qwen3.5-9B-4bit`）

### 安装

```bash
git clone https://github.com/dahai80/fusion-health.git
cd fusion-health
pip install -e ".[test]"

# 如需 API 服务器支持
pip install -e ".[api]"
```

### 处理医疗记录

```bash
# 生成临床摘要
fusion-health ehr summary --input=clinical_notes.txt --output=summary.json

# 生成出院摘要
fusion-health ehr discharge --input=admission_notes.txt --output=discharge.md

# 提取生命体征
fusion-health ehr vitals --input=progress_notes.txt
```

### 医疗编码

```bash
# 推荐 ICD-10 编码
fusion-health code icd10 --input="患者患有高血压和糖尿病"

# 推荐 CPT 编码
fusion-health code cpt --input="Office visit, level 3"

# 审计保险理赔
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

### API 服务器

```bash
# 仅本地（默认）：来自 127.0.0.1 的请求无需 key 即可访问
uvicorn fusion_health.api.app:app --host 127.0.0.1 --port 11469

# 对外暴露：必须设 API key，否则远程请求返回 401
FUSION_HEALTH_API_KEY=your-secret uvicorn fusion_health.api.app:app --host 0.0.0.0 --port 11469
```

> 安全：未设 `FUSION_HEALTH_API_KEY` 时，`/api/*` 端点仅接受 localhost（`127.0.0.1`/`::1`）请求，非 localhost 返回 401。绑定 `0.0.0.0` 或任何非回环地址前，务必设置 `FUSION_HEALTH_API_KEY`；客户端通过 `X-API-Key` 头传递。

### 生命周期管理 (start.sh)

后台 detach 启动/停止/状态，供 fusion-studio 集成 — 端口 11469（从 11456 迁移，避免与 fusion-simulation-metrics 冲突）。

```bash
./start.sh start    # nohup uvicorn ... --host 127.0.0.1 --port 11469（PID 文件 .fusion-health.pid）
./start.sh stop     # 优雅 SIGTERM，5s 后回退 SIGKILL
./start.sh status   # 输出 "running (pid N, port 11469)" / "stopped"；退出码 0/1
./start.sh restart  # 先停后启
```

通过环境变量覆盖默认值：`FUSION_HEALTH_PORT`、`FUSION_HEALTH_HOST`。

### fusion-gateway 对接

fusion-health 连接 **fusion-gateway**（端口 `11432`），由 gateway 代理至本地 fusion-mlx 推理引擎。gateway 用 API key 鉴权，无需路由头：

```bash
export FUSION_HEALTH_MLX_URL=http://localhost:11432/v1      # fusion-gateway 端点（默认）
export FUSION_MLX_API_KEY=<your-gateway-key>                 # gateway API key（如 fg-admin-key）
```

`FUSION_MLX_API_KEY` 为标准 key 来源；`FUSION_HEALTH_MLX_API_KEY` 作为别名兼容。若两者均未设，fusion-health 自动从 `~/.fusion-mlx/settings.json`（`auth.api_key`）读取 key，直连 mlx 场景开箱即用。若需绕过 gateway 直连 fusion-mlx（端口 `11434`），另设 `FUSION_HEALTH_MLX_ROUTE=chat` 以发送必需的 `X-Fusion-Route` 头。

### 多轮对话

```bash
# 启动交互式对话
fusion-health chat --system-prompt="你是一个医疗AI助手"

# 继续已保存的会话
fusion-health chat --session=saved_session.json
```

### 批量处理

```bash
# 处理目录下所有 .txt 文件
fusion-health batch --dir=./cases --action=ehr_summary --output-dir=./results

# 可用动作: ehr_summary, ehr_vitals, code_icd10, compliance_audit, tcm_analyze
# 用 --concurrency 控制并发数（默认: 3）
```

### 模板渲染

```bash
# 列出可用模板
fusion-health template list

# 用数据渲染模板
fusion-health template render discharge_summary --data='{"patient_name":"张三","diagnosis":"高血压","hospital_course":"降压治疗"}'

# 在自定义目录初始化默认模板
fusion-health template init --dir=./my_templates
```

### TUI（终端界面）

```bash
# 启动交互式终端界面
fusion-health tui
```

#### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health` | 健康检查 |
| `POST` | `/api/v1/ehr/summary` | 生成临床摘要 |
| `POST` | `/api/v1/ehr/summary/stream` | SSE 流式临床摘要 |
| `POST` | `/api/v1/ehr/discharge` | 生成出院摘要 |
| `POST` | `/api/v1/ehr/discharge/stream` | SSE 流式出院摘要 |
| `POST` | `/api/v1/ehr/vitals` | 提取生命体征 |
| `POST` | `/api/v1/insurance/icd10` | 推荐 ICD-10 编码 |
| `POST` | `/api/v1/insurance/icd10/stream` | SSE 流式 ICD-10 编码 |
| `POST` | `/api/v1/insurance/cpt` | 推荐 CPT 编码 |
| `POST` | `/api/v1/insurance/cpt/stream` | SSE 流式 CPT 编码 |
| `POST` | `/api/v1/insurance/claim-audit` | 审计保险理赔 |
| `POST` | `/api/v1/insurance/drg` | 推荐 DRG 分组 |
| `POST` | `/api/v1/insurance/catalog` | 匹配医保目录 |
| `POST` | `/api/v1/insurance/procedure-codes` | 推荐手术编码 (ICD-9-CM-3) |
| `POST` | `/api/v1/literature/search` | 检索临床文献 |
| `POST` | `/api/v1/literature/evidence` | 循证摘要 |
| `POST` | `/api/v1/literature/evidence/stream` | SSE 流式循证摘要 |
| `POST` | `/api/v1/compliance/audit` | 审计文档合规 |
| `POST` | `/api/v1/compliance/audit/stream` | SSE 流式合规审计 |
| `POST` | `/api/v1/compliance/regulatory` | 检查法规合规 |
| `POST` | `/api/v1/compliance/regulatory/stream` | SSE 流式法规检查 |
| `POST` | `/api/v1/tcm/analyze` | 中医完整分析 |
| `POST` | `/api/v1/tcm/analyze/stream` | SSE 流式中医分析 |
| `POST` | `/api/v1/tcm/syndrome` | 中医辨证 |
| `POST` | `/api/v1/tcm/formula` | 推荐方剂 |
| `POST` | `/api/v1/tcm/contraindications` | 检查中药配伍禁忌 |
| `POST` | `/api/v1/chat/start` | 开始对话会话 |
| `POST` | `/api/v1/chat/message` | 发送对话消息 |
| `POST` | `/api/v1/chat/message/stream` | SSE 流式对话响应 |
| `POST` | `/api/v1/chat/save` | 保存对话会话 |
| `GET` | `/api/v1/chat/sessions` | 列出活跃会话 |
| `DELETE` | `/api/v1/chat/sessions/{id}` | 删除对话会话 |

---

## CLI 参考

| 命令 | 说明 |
|------|------|
| `ehr summary --input [--output]` | 生成结构化临床摘要 |
| `ehr discharge --input [--output]` | 生成出院摘要 |
| `ehr vitals --input` | 提取生命体征 |
| `code icd10 --input` | 推荐 ICD-10 诊断编码 |
| `code cpt --input` | 推荐 CPT 手术编码 |
| `code audit --input` | 审计保险理赔 |
| `literature <query> [--max-results]` | 检索临床文献 |
| `compliance audit --input` | 审计临床文档 |
| `compliance regulatory --input --type` | 检查法规合规 |
| `chat [--session] [--system-prompt]` | 交互式多轮对话 |
| `batch --dir --action [--output-dir] [--concurrency]` | 批量处理文件 |
| `template list` | 列出可用模板 |
| `template render <name> --data` | 用数据渲染模板 |
| `template init [--dir]` | 初始化默认模板 |
| `tui` | 启动终端界面 |
| `version` | 显示版本 |

---

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│              Fusion-Health 接口层                                 │
│  CLI · TUI · Chat · Batch · Template · API (FastAPI REST + SSE)  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     核心引擎                                     │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ EHRProcessor   │  │ InsuranceCoder │  │ LiteratureRetriever│ │
│  │ · 摘要         │  │ · ICD-10 编码  │  │ · 临床检索        │  │
│  │ · 出院         │  │ · CPT 编码     │  │ · 循证摘要        │  │
│  │ · 体征         │  │ · 理赔审计     │  │                  │  │
│  │ + FHIRMapper   │  │ + ICDValidator │  │ + PubMedClient   │  │
│  └────────────────┘  └────────────────┘  │ + SemanticScholar│  │
│                                           └──────────────────┘  │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐ │
│  │ ComplianceChecker    │  │ TCMAssistant                    │ │
│  │ + RuleEngine         │  │ · 辨证 · 方剂 · 十八反          │ │
│  └──────────────────────┘  └─────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ ConversationMem  │  │ BatchProcessor   │  │ TemplateEngine│ │
│  │ · 多轮对话       │  │ · 并发控制       │  │ · Jinja2      │ │
│  │ · 保存/加载      │  │ · 5 种动作       │  │ · 3 个内置    │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LLMGateway · HealthConfig · Pydantic Schemas · SSE Stream │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP API
┌───────────────────────────▼─────────────────────────────────────┐
│                    fusion-mlx (/v1/chat/completions)              │
│                    Apple Silicon MLX 运行时                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 与 Claude Health 对比

| 能力 | Claude Health | Fusion-Health |
|------|-------------|--------------|
| EHR 临床摘要 | ✅ | ✅ |
| 出院摘要 | ✅ | ✅ |
| 生命体征提取 | ✅ | ✅ |
| ICD-10 编码 | ✅ | ✅ |
| CPT 编码 | ✅ | ✅ |
| 理赔审计 | ✅ | ✅ |
| 文献检索 | ✅ | ✅ |
| 循证摘要 | ✅ | ✅ |
| 文档审计 | ✅ | ✅ |
| 法规合规 | ✅ | ✅ |
| **本地离线** | ❌ 仅云端 | ✅ **100% 本地** |
| **数据隐私** | ❌ PHI 上传 | ✅ **数据不离设备** |
| **中国合规** | ❌ 违反 PIPL | ✅ **完全合规** |
| **零 API 费用** | ❌ 企业订阅 | ✅ **免费** |
| **中医支持** | ❌ 有限 | ✅ **原生支持** |

---

## 更新日志

### v1.0.9 — 安全与医疗安全审计修复

对抗式审计发现 7 项阻塞 + 约 20 项 P0–P3 问题，覆盖安全、并发、医疗安全、性能。已全部修复。

**安全 (F1–F4)**
- 重写 `APIKeyMiddleware`：默认拒绝、路径归一化（防御 `//api//...` 绕过）、owner-id 注入（key 的 sha256）。非回环地址无 key 请求返回 401。
- 对话会话以 `(owner_id, session_id)` 为键 — 一个 owner 无法读取/列出/删除另一个 owner 的会话。`MAX_SESSIONS=1000`，按 owner LRU 淘汰并关闭 gateway。
- SSE 流式加固：15s 心跳、客户端断连检测、`finally` 中清理 gateway、`on_done` 回调将助手消息落盘到历史（流式与非流式历史一致）。
- 中医 `analyze` 通过 `TCMAnalysisResult` schema 校验 LLM 输出，标记 `ai_generated_unverified`（不作为权威结论呈现）。EHR `ClinicalSummary`/`VitalsResult` 携带相同 `source` 标记 + 告警日志。

**并发与内存 (B1–B6)**
- `ConversationMemory` 系统消息处理：`add_system_message` 原地更新，`_trim_short_term` 保留系统消息，淘汰最旧的 user/assistant 轮次到长期记忆。`load()` 校验消息角色，跳过异常条目。
- `BatchProcessor` 结果/错误为单次运行的局部变量（无跨运行泄漏）；文件 I/O 卸载到线程。
- 会话删除与淘汰调用 `session.close()`（释放 LLM gateway）。

**医疗安全 (A1–A5)**
- 中医症状匹配处理否定（`不/无/未/没/非/勿/否`），"无发热" 不再匹配 "发热"。
- ICD/DRG/目录数据库按 `data_dir` 在类级别缓存（每进程解析一次，非每请求），实例仍按请求创建以兼容 mock。
- CLI `_safe_input`/`_safe_output` 辅助函数校验路径并创建父目录。
- ehr/insurance/literature/compliance/tcm 的 SSE 路由将 gateway 传给 `sse_response` 以便清理。

**性能 (P1–P3)**
- `LiteratureRetriever` 通过 `asyncio.gather` 并行拉取 PubMed + Semantic Scholar（DOI 去重保留）。
- PubMed / Semantic Scholar / Artifact 客户端使用惰性实例级 `httpx.AsyncClient` + `aclose()`。

**测试 (M3)**
- 新增 `tests/test_audit_security.py`：中间件路径绕过、会话 owner 隔离、流式历史一致性。148 项测试通过，`ruff check .` 干净。

### v1.0.8 — 端口冲突与 CI 修复

API 端口从 11456 迁移到 11469（避免与 fusion-simulation-metrics 冲突，关闭 #16）。CI 修复（ruff + api extras）。动态版本。

### v1.0.7 — 生产加固

CI、开箱即用 API key、API 鉴权默认开启。

---

## 许可证

[Apache License 2.0](LICENSE)

## 致谢

- [fusion-mlx](https://github.com/dahai80/fusion-mlx) — Apple Silicon 模型服务
- [Claude Health](https://www.anthropic.com/healthcare) — 参考架构
