# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Hermes 分层记忆 provider 插件:SQLite 为权威存储,LanceDB(不可用时降级为本地
stub)提供语义索引。唯一插件为 `layered_lancedb_sqlite`。完整记忆规范见
[`README.md`](README.md) 的 "Memory Specification" 章节。

## 常用命令

```bash
# 安装依赖
uv pip install -e ".[dev]"

# 代码格式化
ruff format

# Lint 并自动修复
ruff check --fix

# 运行所有测试
pytest tests/

# 运行单个测试
pytest tests/test_provider.py -k "test_name"

# 运行测试并生成覆盖率报告
pytest --cov=plugins --cov-report=term-missing

# CLI 命令(维护工具)
hermes layered_lancedb_sqlite validate
hermes layered_lancedb_sqlite rebuild-index
hermes layered_lancedb_sqlite purge-expired --profile <p> --workspace <w>  # dry run
hermes layered_lancedb_sqlite purge-expired --profile <p> --workspace <w> --apply
```

## 版本号管理

- **当前版本:`0.6.1`**
- 采用语义化版本 [SemVer](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`:
  - `MAJOR` — 不兼容的存储格式 / 隔离语义 / 接口变更(需手动且不向后兼容的迁移)
  - `MINOR` — 向后兼容的新能力(新 header、新字段、新 CLI 命令、新配置项)
  - `PATCH` — 向后兼容的修复、重构、文档
- 版本号有三处副本,**必须始终保持一致**:
  1. `pyproject.toml` 的 `version`(权威来源 / SSOT)
  2. `CHANGELOG.md` 顶部的版本条目
  3. 本文件「当前版本」

### 每次更新的强制流程

任何实质性变更(功能 / 修复 / 迁移 / 行为变化)在 **commit 前必须**:

1. 按 SemVer 递增 `pyproject.toml` 的 `version`;
2. 在 `CHANGELOG.md` 顶部新增对应条目(日期 + `Added` / `Changed` / `Fixed` /
   `Migration` 分节);
3. 把本文件的「当前版本」更新为同一版本号;
4. 若涉及存储 schema、隔离、迁移,同步更新 `README.md` 的规范与 "Upgrading" 章节。

> 仅 typo / 注释一类无影响的微调可不升版本;有疑问时一律升一个 `PATCH`。

## 提交前检查

- `ruff check --fix` 与 `ruff format` 通过
- `pytest tests/` 全绿
- 版本号三处一致(见上)

## 项目结构

```
.
├── plugins/memory/layered_lancedb_sqlite/  # 规范实现位置
│   ├── __init__.py                         # Provider 入口
│   ├── storage.py                          # SQLite + LanceDB 存储层
│   ├── namespace.py                        # 命名空间与身份解析
│   ├── policy.py                           # 策略决策中心
│   ├── recall_service.py                   # 分层召回组装
│   ├── promotion_service.py                # 轮次整合与持久化提升
│   ├── memory_write_service.py             # 显式记忆镜像
│   ├── maintenance_service.py              # 每日用户维护
│   ├── prompt_format.py                    # 记忆格式化
│   ├── background.py                       # 后台任务管理
│   ├── governance.py                       # 置信度评分与排序
│   ├── config.py                           # 配置管理
│   ├── cli.py                              # CLI 命令
│   └── identity_sidecar.py                 # 身份缓存
├── tests/                                  # 测试文件
├── pyproject.toml                          # 项目配置
├── CHANGELOG.md                            # 版本历史
└── README.md                               # 完整文档
```

> 根目录的同名模块(`storage.py`、`namespace.py` 等)仅为兼容 shim,实际逻辑在
> `plugins/memory/layered_lancedb_sqlite/` 中。不要修改根目录模块,除非是为了维护
> 向后兼容的导入路径。

## 架构概览

### 分层存储

- **SQLite**: 权威存储层,所有记忆记录的 canonical source
- **LanceDB**: 语义向量索引(不可用时降级为本地 stub,保持重建契约)
- 存储路径:`<hermes_home>/memory-providers/layered_lancedb_sqlite/<profile>/<workspace>/`

### 记忆层级

| 层级 | 作用域 | 用途 |
|------|--------|------|
| `episodic` | 会话绑定 | 逐轮上下文,每轮写入(`importance=0.35`, `source=sync_turn`) |
| `semantic_user` | 用户持久化 | 长期用户记忆(仅 gateway 用户) |
| `semantic_shared` | 工作区共享 | 工作区内所有用户共享的知识 |

### 核心服务职责

- **storage.py**: SQLite + LanceDB 操作、embedding 生成、schema 迁移(`_ensure_column` 幂等模式)
- **namespace.py**: 从 headers/kwargs 解析身份,构建 `RuntimeContext`
- **policy.py**: 集中化策略决策 —— 共享意图、写入授权、目标层级、principal 选择、召回范围
- **recall_service.py**: 分层召回组装(episodic + semantic)、强化
- **promotion_service.py**: 轮次整合、持久化提升(置信度 ≥ `promotion_min_score`)、重复检测
- **memory_write_service.py**: 用户请求中的显式记忆镜像
- **maintenance_service.py**: 每日用户维护(每个 profile/workspace/date 幂等)
- **governance.py**: 置信度评分、指纹生成、supersession 启发式
- **background.py**: 待处理 future 跟踪、drain 管理、错误捕获

### 身份与隔离

- **Principal 解析优先级**: `user_email` → `user_id_alt`(若 `prefer_user_id_alt`)→ `user_id` → `__shared__`
- **Gateway 分类**: 请求携带身份 OR platform 非 CLI → gateway(私有隔离)
- **命名空间隔离**: `profile_id` → `workspace_id` → `principal_id` → `session_id`(仅 episodic)→ `layer`
- **接受的 Headers**: `X-Hermes-*` 或 `X-OpenWebUI-*`(key 大小写不敏感)
- **身份持久化**: 每条记忆行存储 `user_id`、`user_email`、`user_name`,便于溯源

### Thin Provider 模式

Provider 采用"瘦 provider"模式:
- `LayeredLanceDBSQLiteMemoryProvider` 是 Hermes 面向的适配器
- 所有业务逻辑委托给专注的服务(policy、recall、promotion 等)
- 策略决策集中在 `policy.py` —— 无分散的条件判断
- Provider 仅编排服务,不拥有实现细节

### Hermes 兼容性

- **Hermes 0.18-0.21**: 当前版本兼容(已验证至 v2026.9.21)
- 实现 hooks: `prefetch`、`sync_turn`、`on_session_switch`、`on_session_end`、`on_memory_write`、`shutdown`
- `on_session_switch(rewound=True)` 处理 `/undo` 缓存失效
- Drain 超时降至 3s,以适应 Hermes 0.19+ 的 5s shutdown budget
- **向后兼容机制**: Hermes 0.20+ 的 `sync_turn` 新增 `messages` 和 `turn_author` 可选参数,通过签名检测自动适配(插件不实现也不会报错)
- **PyPI vs GitHub**: PyPI 最新版本为 0.19.0,GitHub 最新为 0.21.4 — 插件兼容两者

### 重要模式

- **不可变性**: DTO 使用 `@dataclass(frozen=True)`(`SharedIntentDecision`、`WriteDecision`、`RecallScope`)
- **幂等迁移**: Schema 变更使用 `_ensure_column` 模式,可安全多次运行
- **后台任务管理**: `BackgroundTasks` 跟踪 pending futures,带 drain 超时
- **Embedding 稳定性**: `EMBEDDER_VERSION` 常量在 embedding 算法变更时触发索引重建

## 测试要求

- 提交前所有测试必须通过
- 使用 `pytest` 进行单元和集成测试
- 测试文件位于 `tests/`
- 覆盖率目标:80%+
- 运行单个测试:`pytest tests/test_provider.py -k "test_name"`

## 代码风格

- 所有函数签名使用类型提示
- 遵循 PEP 8 约定
- 使用 `ruff` 进行格式化和 linting
- 提交前运行 `ruff format` 和 `ruff check --fix`
- DTO 使用 `@dataclass(frozen=True)` 保证不可变性
- 错误处理:显式处理,不静默吞掉异常
