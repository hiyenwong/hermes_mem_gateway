上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# CLI 模块

> 维护 CLI 模块，提供存储验证、索引重建和每日用户记忆维护命令。

## 概述

CLI 模块暴露 Hermes 维护 CLI 子命令，用于验证存储状态、重建语义索引，以及由 Hermes/外部调度器显式触发每日用户记忆维护。命令通过 Hermes CLI 框架注册，路径为：

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
hermes layered_lancedb_sqlite compact-user --profile coder --workspace workspace-a --date 2026-05-28 --user-email doris@example.com
hermes layered_lancedb_sqlite compact-daily --profile coder --workspace workspace-a --date 2026-05-28
```

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| `register_cli(subparser)` | 函数 | 注册 CLI 子命令 |
| `run_cli(args, hermes_home)` | 函数 | 执行 CLI 命令 |

## 命令说明

### `validate`

验证存储状态，返回 JSON 报告：

```json
{
  "sqlite_exists": true,
  "memory_count": 42,
  "index_backend": "lancedb",
  "index_path": "/path/to/lancedb"
}
```

### `rebuild-index`

从 SQLite 重建语义索引，返回重建记录数：

```json
{
  "rebuilt": 15
}
```

### `compact-user`

对单个 Gateway 用户执行每日维护。必须提供稳定身份 `--user-email` 或 `--user-id`，display name 只用于 provenance。

```bash
hermes layered_lancedb_sqlite compact-user \
  --profile coder \
  --workspace workspace-a \
  --date 2026-05-28 \
  --user-email doris@example.com
```

输出 JSON 包含 `status`、`principal_id`、`processed_count`、`archived_count`、`output_memory_id` 和 `skipped`。

### `compact-daily`

枚举当前 profile/workspace 下已有 `semantic_user` principal，逐个运行每日维护。

```bash
hermes layered_lancedb_sqlite compact-daily \
  --profile coder \
  --workspace workspace-a \
  --date 2026-05-28
```

输出 JSON 包含 `processed_principals`、`completed`、`failed`、`skipped` 和每个 principal 的结果。

## 依赖关系

- 依赖：[Config](config.md)、[Storage](storage.md)、Maintenance Service
- 被依赖：Hermes CLI 框架

## 参见

- [API 参考](../api.md#validate_storage)
- [开发指南](../developer_guide.md)
