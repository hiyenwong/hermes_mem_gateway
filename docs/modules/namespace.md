上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# Namespace 模块

> 命名空间模块，负责解析用户身份和构建分区键。

## 概述

Namespace 模块定义了运行时上下文（RuntimeContext）和命名空间上下文（NamespaceContext）两个核心数据类，以及身份解析逻辑：

- **RuntimeContext** — 描述当前会话的平台、智能体身份、用户信息
- **NamespaceContext** — 描述记忆存储的 profile、workspace、principal、session、platform 和 metadata facts

命名空间解析流程从 kwargs 参数中提取用户身份（支持 OpenWebUI Headers），根据平台类型判断是否为 Gateway 用户。durable 写入授权、目标层和 principal 选择由 [Policy](policy.md) 统一决策。

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| [`RuntimeContext`](../data_models.md#runtimecontext) | 类 | 运行时上下文数据类 |
| [`NamespaceContext`](../data_models.md#namespacecontext) | 类 | 命名空间上下文数据类 |
| `SHARED_PRINCIPAL` | 常量 | 共享主体标识（`__shared__`） |
| `resolve_namespace(config, runtime)` | 函数 | 解析命名空间上下文 |
| `runtime_from_kwargs(session_id, **kwargs)` | 函数 | 从 kwargs 构建 RuntimeContext |

## OpenWebUI Headers 映射

| Header | 字段 |
|--------|------|
| `X-OpenWebUI-User-Email` | `user_email` |
| `X-OpenWebUI-User-Id` | `user_id` |
| `X-OpenWebUI-User-Name` | `user_name` |

身份优先级：`user_email` > `user_id` > `user_name`（display name 不作为 principal_id）

## 上下文事实

- Gateway 请求优先解析 `user_email`，其次解析 `user_id`
- display name 只作为提示上下文，不作为 durable principal key
- 非 Gateway 请求使用 `__shared__` 作为 shared principal marker
- `agent_context`、`request_metadata` 和 `metadata_shared_intent` 会保留给 Policy 决策

## 依赖关系

- 依赖：[Config](config.md)（ProviderConfig 类型引用）
- 被依赖：[MemoryProvider](memory_provider.md)、[Policy](policy.md)

## 参见

- [API 参考](../api.md)
- [数据模型](../data_models.md#namespacecontext)
- [术语表](../glossary.md#principal-id)
