# 架构合规整改计划

> 审计日期: 2026-08-02
> 关联 Issue: #2
> 违规等级: P1
> 合规评级: C

## 层级定位

**五、垂直行业产品** — 健康

## 违规项与整改

| # | 违规项 | 整改方案 | 截止 |
|---|--------|----------|------|
| 1 | fusion_health/llm_gateway.py 绕过 fusion-core 自建完整 LLM 网关 | 改为使用 fusion_core.mlx_client.FusionMLXClient | P1-S1 |
| 2 | _parse_structured() 结构化输出解析 | 贡献到 fusion-core 而非各自实现 | P1-S2 |

## 对标合规项目

fusion-finance、fusion-k12-teacher 正确使用 FusionMLXClient，应以他们为标杆。

## 合规标准

- 使用 fusion_core.mlx_client.FusionMLXClient
- 不自建 LLM 客户端/网关
