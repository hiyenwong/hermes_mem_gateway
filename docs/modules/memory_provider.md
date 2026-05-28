上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# MemoryProvider 模块

> 插件主入口，实现 Hermes MemoryProvider 接口，协调配置、命名空间、存储、Policy 和服务模块。

## 概述

`LayeredLanceDBSQLiteMemoryProvider` 是本插件的核心类，位于规范实现路径 `plugins/memory/layered_lancedb_sqlite/__init__.py`。它实现了 Hermes 的 MemoryProvider 接口，通过一系列钩子方法（hooks）提供服务：

- `initialize` — 初始化提供者，加载配置并启动存储层
- `prefetch` / `queue_prefetch` — 预取召回上下文
- `sync_turn` — 同步对话回合，触发记忆升级
- `on_session_switch` / `on_session_end` — 会话生命周期管理
- `on_memory_write` — 处理显式记忆写入请求
- `shutdown` — 关闭时清理资源

该类作为 Hermes adapter 和生命周期协调器存在。召回、升级、显式写入、上下文格式化和后台任务处理由 `recall_service.py`、`promotion_service.py`、`memory_write_service.py`、`prompt_format.py` 和 `background.py` 承担。

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| [`LayeredLanceDBSQLiteMemoryProvider`](../api.md#layeredlancedbsqlitememoryprovider) | 类 | 插件主类 |
| [`register()`](../api.md#register) | 函数 | 插件注册入口，返回提供者实例 |

## 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `_hermes_home` | `str` | Hermes home 目录路径 |
| `_config` | [`ProviderConfig`](../data_models.md#providerconfig) | 配置对象 |
| `_runtime` | [`RuntimeContext`](../data_models.md#runtimecontext) | 运行时上下文 |
| `_namespace` | [`NamespaceContext`](../data_models.md#namespacecontext) | 命名空间上下文 |
| `_store` | [`SQLiteStore`](../data_models.md#sqlitestore) | 存储实例 |
| `_background` | `BackgroundTasks` | 后台任务队列、drain 和错误记录 |
| `_prefetch_cache` | `dict` | 预取结果缓存（按 namespace + query 分区） |

## 内部方法

| 方法 | 说明 |
|------|------|
| `_active_namespace` | 解析指定 session_id 的命名空间上下文 |
| `_active_namespace` | 解析指定 session_id 的命名空间上下文 |
| `_require_store` | 获取已初始化的 SQLiteStore |

## 依赖关系

- 依赖：[Config](config.md)、[Namespace](namespace.md)、[Policy](policy.md)、[Storage](storage.md)、[Governance](governance.md)
- 被依赖：Hermes 框架（通过 `plugin.yaml` 注册）

## 参见

- [API 参考](../api.md)
- [数据模型](../data_models.md)
- [架构说明](../architecture.md)
