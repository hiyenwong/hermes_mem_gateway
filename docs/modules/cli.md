上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# CLI 模块

> 维护 CLI 模块，提供存储验证和索引重建命令。

## 概述

CLI 模块暴露 Hermes 维护 CLI 子命令，用于验证存储状态和重建语义索引。命令通过 Hermes CLI 框架注册，路径为：

```bash
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
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

## 依赖关系

- 依赖：[Config](config.md)、[Storage](storage.md)
- 被依赖：Hermes CLI 框架

## 参见

- [API 参考](../api.md#validate_storage)
- [开发指南](../developer_guide.md)