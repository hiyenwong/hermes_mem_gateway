上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# Config 模块

> 配置管理模块，负责加载 YAML 配置、解析环境变量覆盖、合并配置层级。

## 概述

Config 模块定义了 [`ProviderConfig`](../data_models.md#providerconfig) 数据类和一系列配置加载/保存函数。配置来源有三个层级：

1. **YAML 配置文件** — `<hermes_home>/memory-providers/layered_lancedb_sqlite/config.yaml`
2. **全局环境变量** — `<hermes_home>/.env`
3. **Profile 环境变量** — `<hermes_home>/profiles/<profile_id>/.env`

层级优先级：Profile 环境变量 > 全局环境变量 > YAML 配置 > 默认值。

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| [`ProviderConfig`](../data_models.md#providerconfig) | 类 | 配置数据类 |
| [`load_config(hermes_home)`](../api.md#load_config) | 函数 | 从 YAML 加载配置 |
| [`save_config(values, hermes_home)`](../api.md#save_config) | 函数 | 保存配置到 YAML |
| `load_env_overrides(hermes_home, profile_id)` | 函数 | 加载环境变量覆盖 |
| `merge_overrides(config, values)` | 函数 | 合并配置覆盖 |

## 环境变量映射

| 环境变量 | 配置字段 |
|----------|----------|
| `LAYERED_MEMORY_WORKSPACE` | `memory_workspace` |
| `LAYERED_MEMORY_PROFILE_ID` | `profile_id` |
| `LAYERED_MEMORY_ALLOW_NON_PRIMARY_DURABLE_WRITES` | `allow_non_primary_durable_writes` |
| `LAYERED_MEMORY_SHARED_WRITER_EMAILS` | `shared_writer_emails` |
| `LAYERED_MEMORY_SHARED_EXPLICIT_REQUIRED` | `shared_explicit_required` |
| `LAYERED_MEMORY_PROMOTION_MIN_SCORE` | `promotion_min_score` |
| `LAYERED_MEMORY_RECALL_LIMIT_PER_LAYER` | `recall_limit_per_layer` |
| `LAYERED_MEMORY_EMBEDDING_DIMENSIONS` | `embedding_dimensions` |
| `LAYERED_MEMORY_GATEWAY_PLATFORMS` | `gateway_platforms` |
| `LAYERED_MEMORY_STORAGE_ROOT` | `storage_root` |

## 辅助函数

| 函数 | 说明 |
|------|------|
| `config_path(hermes_home)` | 返回 YAML 配置文件路径 |
| `hermes_env_path(hermes_home)` | 返回全局 .env 文件路径 |
| `profile_env_path(hermes_home, profile_id)` | 返回 Profile .env 文件路径 |
| `parse_env_file(path)` | 解析 .env 文件为字典 |
| `coerce_bool(value)` | 将字符串转换为布尔值 |

## 依赖关系

- 依赖：PyYAML
- 被依赖：[MemoryProvider](memory_provider.md)、[CLI](cli.md)

## 参见

- [API 参考](../api.md)
- [数据模型](../data_models.md#providerconfig)
- [开发指南](../developer_guide.md#环境变量)