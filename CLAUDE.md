# CLAUDE.md — hermes_mem_gateway

Hermes 分层记忆 provider 插件:SQLite 为权威存储,LanceDB(不可用时降级为本地
stub)提供语义索引。唯一插件为 `layered_lancedb_sqlite`。完整记忆规范见
[`README.md`](README.md) 的 "Memory Specification" 章节。

## 版本号管理

- **当前版本:`0.3.1`**
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
