上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# Storage 模块

> 存储层模块，包含 SQLiteStore 权威存储和 SemanticIndex 语义索引。

## 概述

Storage 模块是本插件的核心存储层，采用双层设计：

- **SQLiteStore** — 权威存储层，使用 SQLite 持久化记忆记录，支持 WAL 模式和并发访问
- **SemanticIndex** — 语义索引层，使用 LanceDB 进行向量检索，当 LanceDB 不可用时回退到 JSON stub

所有记忆记录首先写入 SQLite，语义层（semantic_user、semantic_shared）记录同步更新索引。

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| [`SQLiteStore`](../data_models.md#sqlitestore) | 类 | SQLite 权威存储类 |
| [`SemanticIndex`](#semanticindex) | 类 | 语义索引类 |
| [`SearchResult`](../data_models.md#searchresult) | 类 | 搜索结果数据类 |
| [`embed_text(text, dimensions)`](#embed_text) | 函数 | 生成文本嵌入向量 |
| [`cosine_similarity(a, b)`](#cosine_similarity) | 函数 | 计算余弦相似度 |

## SQLiteStore 方法

| 方法 | 说明 |
|------|------|
| `bootstrap()` | 初始化数据库表和索引 |
| `close()` | 关闭数据库连接 |
| `validate()` | 验证存储状态 |
| `insert_memory(...)` | 插入记忆记录，返回 memory_id |
| `add_provenance(...)` | 添加记忆来源追踪记录 |
| `reinforce(memory_id)` | 增加记忆强化计数 |
| `archive(memory_id)` | 归档记忆记录 |
| `fetch_existing_durable(...)` | 查询现有持久记忆 |
| `search_exact(...)` | 精确匹配查询（用于 episodic） |
| `search_semantic(...)` | 语义向量检索（用于 semantic 层） |
| `eligible_index_rows()` | 返回可索引的语义记忆记录 |
| `rebuild_index()` | 从 SQLite 重建语义索引 |

## 数据库 Schema

### memories 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT | 主键（UUID） |
| `profile_id` | TEXT | 配置分区标识 |
| `workspace_id` | TEXT | 工作空间标识 |
| `principal_id` | TEXT | 主体标识 |
| `session_id` | TEXT | 会话标识 |
| `layer` | TEXT | 记忆层（episodic、semantic_user、semantic_shared） |
| `kind` | TEXT | 记忆类型（turn、explicit_memory、possible_fact 等） |
| `content` | TEXT | 记忆内容 |
| `fingerprint` | TEXT | 内容指纹（SHA1） |
| `source` | TEXT | 来源标识 |
| `status` | TEXT | 状态（active、archived、superseded） |
| `importance` | REAL | 重要度分数 |
| `reinforcement_count` | INTEGER | 强化计数 |
| `access_count` | INTEGER | 访问计数 |
| `supersedes_id` | TEXT | 取代的旧记忆 ID |
| `superseded_by_id` | TEXT | 被新记忆取代的引用 |
| `metadata_json` | TEXT | 元数据 JSON |

### provenance 表

记忆来源追踪，记录每次记忆创建的来源信息。

## 依赖关系

- 依赖：sqlite3（标准库）、lancedb/pyarrow（可选）
- 被依赖：[MemoryProvider](memory_provider.md)、[CLI](cli.md)

## 参见

- [API 参考](../api.md)
- [数据模型](../data_models.md#searchresult)
- [架构说明](../architecture.md)