[文档首页](README.md) > 开发指南

# 开发指南

## 前置条件

- Python ≥ 3.9
- pytest ≥ 8.2.0（用于测试）
- PyYAML、pyarrow、lancedb（运行依赖）

## 环境搭建

```bash
# 克隆仓库
git clone <repo-url>
cd hermes_mem_gateway

# 安装依赖（推荐使用 uv）
uv pip install -r pyproject.toml

# 安装开发依赖
uv pip install pytest
```

## 构建

本项目为纯 Python 包，无需额外构建步骤。如需打包发布：

```bash
# 使用 setuptools 构建
pip install build
python -m build
```

## 测试

```bash
# 运行所有测试
pytest tests/

# 运行单个测试文件
pytest tests/test_provider.py -v

# 查看测试覆盖率
pytest --cov=. --cov-report=term-missing
```

## 目录结构

完整架构说明参见 [架构说明](architecture.md)。

```
hermes_mem_gateway/
├── __init__.py          # 主入口：LayeredLanceDBSQLiteMemoryProvider
├── config.py            # 配置管理：加载、合并、持久化
├── governance.py        # 治理策略：分类、升级、去重
├── namespace.py         # 命名空间：身份解析、权限计算
├── storage.py           # 存储层：SQLite + LanceDB 索引
├── cli.py               # 维护 CLI：验证、重建索引
├── plugin.yaml          # Hermes 插件元数据
├── pyproject.toml       # 项目配置
├── tests/               # 测试目录
│   ├── conftest.py
│   └── test_provider.py
├── docs/                # 文档目录（本 wiki）
│   ├── README.md
│   ├── architecture.md
│   ├── api.md
│   ├── data_models.md
│   ├── developer_guide.md
│   ├── glossary.md
│   └── modules/
│       └── *.md
└── openspec/            # OpenSpec 变更提案目录
```

## 贡献流程

1. Fork 并从 `main` 创建分支
2. 编写测试覆盖新功能或修复
3. 实现变更，确保现有测试通过
4. 运行 `pytest` 和 `ruff check`
5. 提交 PR 并描述变更内容和测试计划

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LAYERED_MEMORY_WORKSPACE` | `default` | 记忆工作空间命名空间 |
| `LAYERED_MEMORY_PROFILE_ID` | `default` | 配置分区标识 |
| `LAYERED_MEMORY_ALLOW_NON_PRIMARY_DURABLE_WRITES` | `false` | 允许非主上下文写持久记忆 |
| `LAYERED_MEMORY_SHARED_WRITER_EMAILS` | `[]` | Shared writer 白名单邮箱 |
| `LAYERED_MEMORY_SHARED_EXPLICIT_REQUIRED` | `true` | 要求显式 shared intent |
| `LAYERED_MEMORY_PROMOTION_MIN_SCORE` | `0.8` | 记忆升级最低置信度 |
| `LAYERED_MEMORY_RECALL_LIMIT_PER_LAYER` | `4` | 每层召回上限 |
| `LAYERED_MEMORY_EMBEDDING_DIMENSIONS` | `64` | 语义向量维度 |
| `LAYERED_MEMORY_GATEWAY_PLATFORMS` | `gateway,discord,slack,telegram,whatsapp` | Gateway 平台列表 |
| `LAYERED_MEMORY_STORAGE_ROOT` | `""` | 自定义存储根路径 |

环境变量可放置在：
- `<hermes_home>/.env` — 全局配置
- `<hermes_home>/profiles/<profile_id>/.env` — Profile 级配置

## 参见

- [架构说明](architecture.md)
- [API 参考](api.md)
- [文档首页](README.md)