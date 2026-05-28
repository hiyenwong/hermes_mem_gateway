上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# Policy 模块

> 集中化策略模块，负责 shared intent、durable 写入授权、目标层、principal、召回 scope 和审计元数据。

## 概述

`policy.py` 是 privacy-sensitive 决策的唯一实现位置。Provider、Promotion Service、Memory Write Service 和 Recall Service 通过 Policy 获取决策，而不是各自重复判断。

## 公开决策对象

| 符号 | 说明 |
|------|------|
| `SharedIntentDecision` | shared-memory 请求结果与来源（metadata、natural_language、none） |
| `WriteDecision` | durable 写入是否允许、目标 layer、目标 principal、reason 和 metadata |
| `MaintenanceWriteDecision` | maintenance context 写入是否允许、目标 layer、principal 和 metadata |
| `RecallScope` | 一次召回需要查询的 layer、principal、session 与标题 |

## 主要函数

| 函数 | 说明 |
|------|------|
| `resolve_shared_intent` | 解析 shared-memory intent，metadata 优先于自然语言 |
| `shared_write_allowed` | 判断 shared durable memory 写入是否授权 |
| `promotion_write_decision` | 为 turn promotion 生成 durable 写入决策 |
| `memory_write_decision` | 为显式 memory write 生成 durable 写入决策 |
| `maintenance_user_write_decision` | 为每日用户维护生成 same-principal 写入决策 |
| `recall_scopes` | 为当前 namespace 生成显式、按顺序的召回 scope |

## 行为摘要

- Gateway primary 且有稳定身份时，默认写入 `semantic_user`
- Gateway shared 写入必须同时满足 allowlist 和 explicit shared intent
- 非 Gateway primary 默认写入 `semantic_shared`
- 非 primary 上下文默认禁止 durable 写入，除非配置显式放开
- `agent_context="maintenance"` 只允许 same-principal `semantic_user` 维护写入
- per-user maintenance 不默认写 `semantic_shared`
- 每个 durable 写入决策包含稳定 `policy_reason` 和 provenance metadata

## 参见

- [Namespace](namespace.md)
- [Governance](governance.md)
- [MemoryProvider](memory_provider.md)
