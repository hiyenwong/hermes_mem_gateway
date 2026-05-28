# Layered LanceDB SQLite Memory Provider

> Hermes 分层记忆提供者插件，以 SQLite 为权威存储，结合 LanceDB 语义索引实现多层召回。

## 项目概述

本插件是 Hermes 智能体框架的 memory provider 实现，提供分层记忆存储与检索能力。规范实现位于 `plugins/memory/layered_lancedb_sqlite/`；仓库根目录的同名模块仅作为兼容 shim，不承载独立业务逻辑。

核心设计理念是：

1. **SQLite 作为权威数据源** — 所有记忆记录持久化到 SQLite，保证数据一致性
2. **LanceDB 语义索引加速召回** — 对语义层记忆（semantic_user、semantic_shared）进行向量检索
3. **三层记忆隔离** — episodic（会话级）、semantic_user（用户级）、semantic_shared（工作空间级）

该插件支持 Gateway 用户隔离、非主上下文权限控制、以及共享记忆写入的精细化治理策略。

## 快速开始

```python
from plugins.memory.layered_lancedb_sqlite import LayeredLanceDBSQLiteMemoryProvider

# 创建提供者实例
provider = LayeredLanceDBSQLiteMemoryProvider()

# 初始化（在 Hermes 环境中由框架调用）
provider.initialize(
    "session-1",
    hermes_home="/path/to/hermes_home",
    agent_identity="default",
    agent_workspace="workspace-a",
    platform="cli",
)

# 同步对话回合，自动触发记忆升级
provider.sync_turn("Remember that I prefer dark roast coffee.", "Noted.")

# 预取召回上下文
recall = provider.prefetch("coffee preferences")

# 关闭时清理异步任务
provider.shutdown()
```

## 文档导航

| 页面 | 内容 |
|------|------|
| [架构说明](architecture.md) | 系统设计、模块图、数据流 |
| [API 参考](api.md) | 所有导出符号的签名与示例 |
| [数据模型](data_models.md) | 核心类型、Schema、枚举 |
| [开发指南](developer_guide.md) | 环境搭建、构建、测试 |
| [术语表](glossary.md) | 领域术语 A–Z |

## 依赖要求

- Python ≥ 3.9
- PyYAML ≥ 6.0
- pyarrow ≥ 16.0.0
- lancedb ≥ 0.6.13（可选，无此依赖时回退到 stub 索引）
- pytest ≥ 8.2.0（开发依赖）
