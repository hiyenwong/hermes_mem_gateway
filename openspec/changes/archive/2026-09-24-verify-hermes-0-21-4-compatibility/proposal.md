# Proposal: Verify Hermes 0.21.4 Compatibility

## Why

当前插件声明支持 Hermes 0.18-0.19,但 Hermes 已发布 0.21.4 版本。需要验证插件在新版本下的兼容性,确保记忆存储、召回、会话管理等核心功能正常工作,并及时更新支持声明。

## What Changes

- 在 Hermes 0.21.4 环境下运行完整测试套件
- 验证 MemoryProvider 接口方法(`prefetch`、`sync_turn`、`on_session_switch` 等)的兼容性
- 检查 Hermes 0.20-0.21 引入的行为变更(如 completed-turn context、session store 重构)是否影响插件
- 修复发现的不兼容问题(如有)
- 更新 `CLAUDE.md`、`README.md`、`CHANGELOG.md` 中的版本兼容性声明
- 若需要代码调整,按 SemVer 递增版本号

## Capabilities

### New Capabilities

无。本次变更为兼容性验证和文档更新,不引入新的行为能力。

### Modified Capabilities

无。现有 spec 定义的行为不变。

> 注:本变更为纯验证/测试/文档性质,无 spec 层面的行为变更。需要在 `.openspec.yaml` 中设置 `skip_specs: true`。

## Impact

- **测试**: 需在 Hermes 0.21.4 环境中执行集成测试
- **文档**: `CLAUDE.md`、`README.md`、`CHANGELOG.md` 需更新兼容性声明
- **代码**: 若发现不兼容,可能涉及 `plugins/memory/layered_lancedb_sqlite/__init__.py` 的 minor 调整
- **依赖**: 需确认 `lancedb`、`pyarrow` 等依赖与 Hermes 0.21.4 无冲突
- **版本**: 若有代码变更,需按 SemVer 递增版本号(预计 PATCH 或 MINOR)
