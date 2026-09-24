# Design: Verify Hermes 0.21.4 Compatibility

## Context

当前插件 `layered_lancedb_sqlite` v0.6.1 声明支持 Hermes 0.18-0.19。Hermes 在 0.20-0.21 版本引入了以下变更:

- **v0.20.2**: Memory providers 接收完整轮次上下文(completed-turn context),而非仅最终响应
- **v0.21.0**: 捆绑的 memory providers 从核心代码模块化移出(结构变更)
- **v0.21.1-0.21.3**: `state.db` session store 连接处理重写和可靠性修复
- **v0.21.4**: 最新稳定版(用户指定)

插件的 MemoryProvider 接口实现(`prefetch`、`sync_turn`、`on_session_switch` 等)在 0.18-0.19 下已验证稳定,但需要确认在 0.21.4 下的行为一致性。

## Goals / Non-Goals

**Goals:**
- 验证插件在 Hermes 0.21.4 环境下的功能正确性
- 确认 MemoryProvider 接口方法签名和调用契约无破坏性变更
- 检测 Hermes 0.20-0.21 行为变更(如 completed-turn context)对插件的影响
- 修复发现的不兼容问题(若有)
- 更新文档声明支持 Hermes 0.18-0.21

**Non-Goals:**
- 不实现 Hermes 0.21 的新特性(如 cron jobs 持久化记忆)
- 不重构插件架构以适配 Hermes 内部模块化变更
- 不升级 `lancedb`、`pyarrow` 等独立依赖(除非发现兼容性冲突)

## Decisions

### 1. 测试策略:分层验证

**决策**: 采用三层测试策略,从单元测试到集成测试逐步验证。

**理由**:
- **单元测试**(pytest): 验证插件内部逻辑无回归,不依赖 Hermes 运行时
- **集成测试**(本地 Hermes 0.21.4 实例): 验证接口调用契约和行为一致性
- **回归测试**(Hermes 0.19 对比): 确认行为无差异

**替代方案**:
- 仅运行现有单元测试 → 不足,无法验证 Hermes 运行时行为
- 直接在 production 环境测试 → 风险过高,无回滚能力

### 2. 接口兼容性验证:重点检查清单

**决策**: 优先验证以下高风险点:

| 检查项 | 风险等级 | 验证方法 |
|--------|----------|----------|
| `on_session_switch(rewound=True)` | 高 | 触发 `/undo` 命令,验证缓存失效 |
| `sync_turn` 上下文完整性 | 高 | 验证接收完整轮次消息(user + assistant) |
| `shutdown()` drain timeout | 中 | 验证在 Hermes 0.21 的 shutdown budget 内完成 |
| `prefetch` 缓存行为 | 中 | 验证 `/new`、`/reset` 后缓存正确清除 |
| Session store 依赖 | 低 | 验证无直接依赖 `state.db` 内部实现 |

**理由**: 这些是 Hermes 0.20-0.21 变更可能影响的关键路径。

### 3. 代码调整策略:最小侵入

**决策**: 若发现不兼容,优先通过配置或 minor 代码调整解决,避免大规模重构。

**理由**:
- 插件架构已验证稳定(Thin Provider 模式)
- Hermes MemoryProvider 接口保持稳定,破坏性变更概率低
- 最小调整降低回归风险

**替代方案**:
- 重构以适配 Hermes 内部模块化 → 过度工程,无必要
- 放弃支持 0.21 → 不符合用户需求

### 4. 文档更新策略:同步三处声明

**决策**: 若验证通过,同步更新以下三处:
1. `CLAUDE.md` "Hermes 兼容性" 章节
2. `README.md` "Upgrading" 章节
3. `CHANGELOG.md` 新增版本条目

**理由**: 遵循项目的版本号管理规则(三处一致)。

## Risks / Trade-offs

### Risk 1: Hermes 0.21.4 环境搭建失败

**场景**: 依赖冲突、安装问题或环境隔离失败。

**Mitigation**:
- 使用独立 conda 环境:`conda create -n hermes-0.21.4 python=3.11`
- 固定依赖版本:`pip install hermes-agent==0.21.4`
- 若失败,回退到 Docker 容器隔离测试

### Risk 2: 发现未预期的接口变更

**场景**: MemoryProvider 接口方法签名或调用契约在 0.21 中发生破坏性变更。

**Mitigation**:
- 优先查阅 Hermes 官方 changelog 和 release notes
- 若变更 minor(如新增可选参数),通过适配代码解决
- 若变更 major(如删除必需方法),评估是否需要分支支持(不推荐)
- 最终方案:锁定支持版本为 0.18-0.19,明确声明不支持 0.21+

### Risk 3: Completed-turn context 导致数据重复

**场景**: v0.20.2 的 completed-turn context 可能导致 `sync_turn` 接收到重复消息,引发重复记忆写入。

**Mitigation**:
- 在集成测试中验证 `sync_turn` 的消息去重逻辑
- 检查 `governance.fingerprint_text` 是否正确识别重复内容
- 若发现问题,在 `sync_turn` 入口增加消息 hash 校验

### Risk 4: Session store 重构影响插件行为

**场景**: Hermes 0.21.1-0.21.3 的 `state.db` 重构可能影响插件的会话管理。

**Mitigation**:
- 确认插件不直接依赖 `state.db` 内部实现
- 验证 `on_session_switch`、`on_session_end` 的调用时机和参数无变化
- 若发现问题,检查是否需要调整 session_id 解析逻辑

### Trade-off: 测试覆盖 vs 时间成本

**决策**: 优先验证核心功能(记忆写入/召回、会话管理),次要功能(CLI 工具、platform 隔离)可在后续版本验证。

**理由**: 快速交付兼容性验证结果,避免过度测试延迟。

## Migration Plan

### 部署步骤

1. **环境准备**
   ```bash
   conda create -n hermes-0.21.4 python=3.11
   conda activate hermes-0.21.4
   pip install hermes-agent==0.21.4
   pip install -e ".[dev]"  # 安装插件
   ```

2. **单元测试**
   ```bash
   pytest tests/ -v --cov=plugins --cov-report=term-missing
   ```
   - 目标:100% 通过,覆盖率 ≥ 80%

3. **集成测试**
   - 启动 Hermes 0.21.4,配置插件
   - 执行手动测试场景(见 tasks.md)
   - 记录所有通过/失败案例

4. **结果评估**
   - 若全部通过:更新文档,发布新版本
   - 若发现问题:修复后重新测试,或记录为已知限制

### 回滚策略

- 若发现严重不兼容且无法快速修复:
  - 保持当前版本(v0.6.1)的支持声明为 Hermes 0.18-0.19
  - 在 README 中添加 "Known Issues" 章节,说明 0.21+ 兼容性问题
  - 后续版本再解决

## Open Questions

无。所有关键决策已在上述章节明确。
