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

### v1.2.0rc1 — 产品级审计 P0–P3 整改（候选发布版本）

第三次产品级审计（5 P0、12 P1、20 P2、约 12 P3）判定 fusion-health 不具备企业级商用发布条件。全部问题已修复：

**P0（阻断级）：**
- 结构化日志（JSON + 轮转文件处理器），API lifespan 注入 `configure_logging()`
- 审计日志 HMAC-SHA256 逐行签名 + 序列计数 + `verify_log_line()` + `0o600` 权限
- 配置 env/YAML 类型转换容错（坏值保留默认 + 告警）
- 所有路由接入审计日志（每个端点 `log_access`）
- CORS 收紧（来源走环境变量，方法/头部受限）
- `/api/v1/metrics` 路由（请求/鉴权/限流计数器）
- `start.sh` 强制 API key 告警 + 端口占用预检 + `doctor` 子命令

**P1（严重级）：**
- CPT 校验器对格式合法码返回 `ai_suggested`（原硬判 `invalid`）
- ICD-10 子码正则 `{1,4}`→`{1,7}`（真实码被截断）
- CLI 新增 `tcm` + `cn-code` 子命令（DRG/目录/ICD-9-CM-3 + 证型/方剂）
- SSE 流式路由前置领域系统提示词（EHR/医保/合规/中医）
- 限流器修复（`deque` + `popleft`，默认 60 rpm）
- 会话清理器移入 lifespan（驱逐/关停前先落盘）
- 健康 `/ready` 端点（数据文件状态 + 会话计数）
- 文献检索结果缓存（10 分钟 TTL）
- 共享池化 LLMGateway 单例（所有流式路由复用同一池化 httpx 客户端，生命周期纳入 API lifespan — 修复每请求新建 gateway 的对象抖动 + 连接生命周期）
- 多 worker 限流告警（`FUSION_HEALTH_WORKERS` 环境变量；进程内限流器在 >1 worker 时记录有效 N×rpm）

**P2（中级）：**
- FHIR 映射器改用 `model_dump()`（移除无用 `import json`）
- 银行卡正则收紧（按发卡行前缀识别）
- 中药库加载加 mtime 失效（原为永久缓存）
- ICD/DRG/目录/ICD-9-CM-3 响应 `data_source` 由 `.data_source` 标记文件读取（数据导入后自动从 `sample` 切到 `full`）
- 批处理根目录限制 + 移除死代码 `ACTION_MAP`
- CI：Linux 矩阵 + 覆盖率 80% 门槛 + pip-audit

**非代码交付：**
- `scripts/ingest_data.py` — 校验并安装权威编码数据集（ICD-10-CN / ICD-9-CM-3 / DRG / 医保目录），导入后写 `.data_source` 标记为 `full`，备份样本。详见 [DATA_SOURCES.md](DATA_SOURCES.md)。
- `DATA_SOURCES.md` — 数据集状态、必需列、导入与回滚步骤、生产准入门槛。
- `COMPLIANCE.md` — PHI 数据流、审计日志、留存策略、部署加固清单、运营方责任（PIPL / HIPAA 对齐）。
- 多 worker 共享限流：`FUSION_HEALTH_RATE_LIMIT_DB`（SQLite 后端，`BEGIN IMMEDIATE` 原子计数插入；>1 worker 时内存回退并告警）。
- 会话 PHI 静态加密（AES-256-GCM，`FUSION_HEALTH_PHI_KEY`：64 位十六进制原始密钥或口令→PBKDF2-HMAC-SHA256 20 万次迭代；未设置时明文回退，向后兼容）。见 `fusion_health/crypto.py`。
- 企业生产就绪门禁（`fusion_health/enterprise.py`）：设 `FUSION_HEALTH_ENTERPRISE=1` 在 API 启动时强制检查 — 数据源为 `full`、API 密钥 / 审计 HMAC 密钥 / PHI 加密密钥 / CORS 来源均已设置；逐项记录失败。`FUSION_HEALTH_ENTERPRISE_HARD=1` 任一失败即拒绝启动（软模式=仅告警）。`/api/v1/health/ready` 返回 `enterprise_ready` + `enterprise_failures`。

**企业商业发布加固：**
- CI 安全扫描 — Bandit SAST（`bandit -r fusion_health`，须零告警）+ pip-audit 依赖 CVE 扫描，均强制（有发现即非零退出）。见 [SECURITY.md](SECURITY.md)。
- `X-Fusion-Disclaimer` 响应头（每个 API 响应）+ CLI 启动日志：仅供参考、不构成诊断、未取得医疗器械注册证书。
- 审计日志轮转 + 完整性校验（`audit.rotate_log`、`audit.verify_log_file` — 检测 HMAC 篡改 + 序列号断号）。
- 灾备备份/恢复 — `scripts/backup.py create|verify`：审计日志 + 会话文件打包为带 sha256 清单的 tar.gz；**审计日志被篡改时中止备份**；`verify` 逐文件比对清单哈希（不自动恢复 — 运营方手动复制以防 PHI 风险）。
- 负载/性能测试 — `scripts/load_test.py`（进程内 ASGI，无网络）+ `tests/test_load.py`（CI）：并发 10-20，测 p50/p95/p99 + 吞吐，SLO 门禁 p95 ≤ 2000ms（`FUSION_HEALTH_LOAD_SLO_MS`）。实测 316 req/s、p95=84ms。
- 临床评估工具链 — `fusion_health/clinical_eval.py` 金标准评估（precision/recall/F1，3 位 ICD 类目匹配）+ `fusion-health eval` CLI。真机验证：5/5 命中、recall=1.00、F1=0.91。真机测试由 `FUSION_HEALTH_REAL_MODEL=1` 门控。
- [REGULATORY.md](REGULATORY.md) — NMPA 医疗器械分类 + II 类注册路径 + 必要人工动作（顾问、QMS、临床医生验证金标准 ≥100 例）。
- [LEGAL.md](LEGAL.md) — 使用条款模板、PIPL 对齐数据处理协议、个人信息保护影响评估模板、责任框架。使用前须经律师审核。

### v1.1.0 — 第二次独立架构审计修复

第二次独立架构师审计发现 6 项 P0、9 项 P1、10 项 P2 及若干 P3 问题，覆盖架构边界、运行时风险、工程实现。P0 全清，P1 除延期 R9 外全清，P2 全清。

**架构 P0 (H1–H6)**
- 对话会话现受 TTL 约束（`FUSION_HEALTH_SESSION_TTL`，默认 1800s），后台 reaper 每 300s 淘汰过期会话 — 修复内存会话无限增长。
- 令牌桶 `RateLimiter` 限流（`FUSION_HEALTH_RATE_LIMIT_RPM`）— 按 owner 返回 429 + `retry_after`，不再无限暴露 API。
- 结构化 PHI 访问审计日志（`fusion_health/audit.py`）：记录 owner、method、path、action、status、`phi_input_hash`（sha256[:16]）+ 长度 — 绝不记录原始 PHI。JSON 追加、线程锁、`FUSION_HEALTH_AUDIT_DISABLED=1` 关闭。
- CORS 中间件置于最外层（在 `APIKeyMiddleware` 之后添加）+ OPTIONS 放行 — 预检不再被鉴权拦截。
- lifespan 不再丢弃注入配置：`create_app(config)` 在启动后存活；关闭时清理所有会话 + 文献客户端。
- `/api/v1/health` 现探测 MLX 后端 `/models`（httpx，5s 超时），不可达时返回 503 `degraded` 及后端错误 — 推理宕机时不再假健康。

**运行时风险 P1 (H7–H9, R1–R6)**
- 验证器 DB 缓存（`ICDValidator`、`ICD9CM3Validator`、`DRGHelper`、`InsuranceCatalogMatcher`）现按 mtime 失效 — 文件改动无需重启进程即可生效。
- ICD-10/CPT 验证三态：`verified`（DB 命中）、`unverified`（格式合法但不在 DB）、`invalid`（格式不符）— 格式匹配不再误判 `valid=True`。
- LLM 网关日志中 PHI 脱敏：解码/schema/校验错误记录 `content_len` 与 `status_code`，绝不记录原始 `content`/`response.text`。
- SSE 流错误路径改为 raise 而非合成错误 token；客户端断连路径发送 `interrupted` 并跳过 `on_done` — 截断内容不再作为完整回复落盘。
- 提示注入锚点：EHR、编码、合规、中医 LLM 调用新增系统提示（`SYSTEM_PROMPT` + `_messages()`）。
- 对话上下文预算：`get_messages` 按 `max_context_chars`（默认 96000）裁剪，保留系统消息 — token 增长有界。

**工程 P2 (R7–R10, E2–E6)**
- 中药药名归一化 + 否定感知禁忌匹配（4 字窗口 + 短语集）— 减少十八反误判。
- 合规规则引擎 `required` 字段检查要求标签边界 — 杜绝子串误报。
- 文献流式提示由文本拼接而非列表 repr 构建。
- `close_all_sessions` / `close_all_clients` 关闭钩子；每请求 `retriever.aclose()` 在 `finally` 中执行。
- `import fusion_health` 不再强依赖 fastapi（惰性 `__getattr__`）。
- 插件工具缓存 `HealthConfig`，不再每次调用重建。

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
