# Hermes 0.21.4 兼容性分析报告

**日期**: 2026-09-24  
**插件版本**: 0.6.1  
**Hermes 版本**: v2026.9.21 (GitHub tag,对应 0.21.4)  
**Hermes PyPI 版本**: 0.19.0 (最新可用)

## 执行摘要

**结论**: ✅ **插件与 Hermes 0.21.4 兼容**

通过代码分析验证,当前插件(`layered_lancedb_sqlite` v0.6.1)与 Hermes 0.21.4 (v2026.9.21) 的 MemoryProvider 接口完全兼容。Hermes 0.19→0.21 的接口变更均为向后兼容的扩展,不会破坏现有插件。

## 关键发现

### 1. 版本不一致问题

| 来源 | 版本 | 说明 |
|------|------|------|
| PyPI (`pip install hermes-agent`) | 0.19.0 | 最新可用的 pip 包 |
| GitHub Release | 0.21.4 (v2026.9.21) | 最新 GitHub tag |
| 当前插件支持声明 | 0.18-0.19 | 匹配 PyPI 版本 |

**发现**: Hermes 0.21.4 存在于 GitHub,但未发布到 PyPI。网络搜索提到的 pip 安装方式已被标记为 "unsupported legacy"。

**影响**: 插件当前已支持 PyPI 上的最新版本(0.19.0)。GitHub 版本需要通过源码安装或 Desktop app 获取。

### 2. MemoryProvider 接口变更分析

#### 2.1 新增方法(可选,不影响兼容性)

Hermes 0.21.4 新增了以下可选方法:

| 方法 | 用途 | 兼容性 |
|------|------|--------|
| `recall_status() -> Optional[RecallStatus]` | 返回最近一次 prefetch 的召回状态 | ✅ 可选,默认返回 None |
| `identity_signature() -> Dict` | 身份映射值,用于缓存失效 | ✅ 可选,默认返回 {} |
| `on_delegation(task, result, **kwargs)` | 子代理委派观察 | ✅ 可选 hook |

**结论**: 这些都是可选方法,插件不实现也不会报错。

#### 2.2 方法签名变更(向后兼容)

**`sync_turn` 签名变更**:

```python
# v2026.7.20 (Hermes 0.18)
def sync_turn(
    self,
    user_content: str,
    assistant_content: str,
    *,
    session_id: str = "",
    messages: Optional[List[Dict[str, Any]]] = None,
) -> None:

# v2026.9.21 (Hermes 0.21.4)
def sync_turn(
    self, user_content: str, assistant_content: str, *,
    session_id: str = "", messages: Optional[List[Dict[str, Any]]] = None,
    turn_author: Optional[Dict[str, Any]] = None,
) -> None:
```

**变更**: 新增 `turn_author` 参数(可选,keyword-only)

**兼容性机制**: Hermes 使用 `_provider_sync_accepts()` 检查插件是否接受新参数:

```python
@staticmethod
def _provider_sync_accepts(provider: MemoryProvider, keyword: str) -> bool:
    """Whether ``sync_turn`` accepts ``keyword`` (uninspectable → assume yes)."""
    params = _signature_params(provider.sync_turn)
    return params is None or _has_var_kwargs(params) or keyword in params
```

**我们的实现**:
```python
def sync_turn(self, user: str, assistant: str, *, session_id: str = "") -> None:
```

**结果**: ✅ **兼容** — Hermes 检测到我们的 `sync_turn` 不接受 `messages` 和 `turn_author`,不会传递这些参数。

#### 2.3 未变更的关键方法

以下方法签名在 0.19→0.21 间**无变化**:

- `prefetch(query, *, session_id="")`
- `on_session_switch(new_session_id, *, parent_session_id="", reset=False, rewound=False, **kwargs)`
- `on_session_end(messages)`
- `on_memory_write(action, target, content, metadata=None)`
- `shutdown()`
- `backup_paths()`

### 3. 行为变更分析

#### 3.1 Completed-turn context (v0.20.2)

**变更**: Memory providers 现在接收完整轮次上下文,而非仅最终响应。

**影响**: `sync_turn` 的 `messages` 参数现在包含完整的 OpenAI-style 消息列表。

**我们的实现**: 当前不使用 `messages` 参数,仅使用 `user` 和 `assistant` 内容。

**结论**: ✅ **无影响** — 我们的实现不依赖 `messages`,行为不变。

#### 3.2 Context thread management (v0.21.0)

**新增**: `spawn_context_thread()` 和 `ctx_bound()` 工具函数,用于在后台任务中保持 contextvars。

**影响**: Hermes 建议所有后台任务使用这些工具函数保持 profile 隔离。

**我们的实现**: 使用自定义的 `BackgroundTasks` 类管理后台任务。

**结论**: ✅ **无冲突** — 我们的实现独立于 Hermes 的 context thread 管理,可以继续使用自己的后台任务机制。未来可以考虑迁移到 Hermes 的工具函数以获得更好的 profile 隔离,但不是必须的。

#### 3.3 Session store 重构 (v0.21.1-0.21.3)

**变更**: `state.db` 连接处理重写,修复 handle leaks。

**影响**: 内部优化,不影响 MemoryProvider 接口。

**我们的实现**: 不直接依赖 `state.db`,使用自己的 SQLite 存储。

**结论**: ✅ **无影响** — 插件使用独立的 SQLite 存储,不受 Hermes session store 重构影响。

### 4. Drain timeout 兼容性

**Hermes 0.19+**: `MemoryManager._SYNC_DRAIN_TIMEOUT_S = 5` 秒  
**我们的实现**: `_SESSION_SWITCH_DRAIN_TIMEOUT_S = 3.0`, `_SHUTDOWN_DRAIN_TIMEOUT_S = 3.0`

**结论**: ✅ **兼容** — 我们的 3s timeout 在 Hermes 的 5s budget 内,留有充足余量。

### 5. 新增特性(未使用)

Hermes 0.21 引入的新特性,当前插件未使用:

- `PRE_COMPRESS_CHECKPOINT_API_VERSION = 2`: 增强的 pre-compress checkpoint API
- `TRIVIAL_PROMPT_RE`:  trivial prompt 检测(跳过 recall)
- `RecallStatus`: 召回状态指示器

**结论**: 这些都是可选优化,不影响基本功能。未来可以考虑实现以提升用户体验。

## 兼容性矩阵

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `prefetch` 方法签名 | ✅ 兼容 | 无变化 |
| `sync_turn` 方法签名 | ✅ 兼容 | 新增可选参数,Hermes 自动检测 |
| `on_session_switch` 方法签名 | ✅ 兼容 | 无变化,已有 `**kwargs` |
| `on_session_end` 方法签名 | ✅ 兼容 | 无变化 |
| `on_memory_write` 方法签名 | ✅ 兼容 | 无变化 |
| `shutdown` drain timeout | ✅ 兼容 | 3s < 5s budget |
| `backup_paths` 返回值 | ✅ 兼容 | 返回空列表,无外部依赖 |
| 新增可选方法 | ✅ 兼容 | 不实现也不会报错 |
| Completed-turn context | ✅ 兼容 | 不使用 `messages` 参数,无影响 |
| Session store 重构 | ✅ 兼容 | 使用独立存储,不受影响 |

## 风险评估

### 低风险

- **接口变更**: 所有变更为向后兼容的扩展
- **行为变更**: 我们的实现不依赖变更的行为
- **Drain timeout**: 有充足余量

### 无风险

- **新增方法**: 可选,不实现不影响
- **Session store**: 使用独立存储
- **Context thread**: 独立实现,无冲突

## 建议

### 短期(当前版本)

1. ✅ **无需代码变更** — 当前实现已兼容 Hermes 0.21.4
2. ✅ **更新文档声明** — 将支持范围从 "0.18-0.19" 更新为 "0.18-0.21"
3. ✅ **添加验证记录** — 在 CHANGELOG 中记录兼容性验证结果

### 中期(未来版本)

1. **可选优化**: 实现 `recall_status()` 以提供召回状态指示器
2. **可选优化**: 使用 `messages` 参数获取更丰富的上下文
3. **可选优化**: 迁移到 `spawn_context_thread()` 以获得更好的 profile 隔离
4. **可选优化**: 实现 `PRE_COMPRESS_CHECKPOINT_API_VERSION = 2` 以支持增强的 checkpoint

### 长期

1. **监控 PyPI**: 等待 Hermes 0.21+ 发布到 PyPI
2. **测试覆盖**: 在 Hermes 0.21.4 环境下运行完整集成测试(需要 Desktop app 或源码安装)

## 测试建议

### 已完成的验证(代码分析)

- ✅ 接口方法签名对比
- ✅ 行为变更影响分析
- ✅ Drain timeout 兼容性检查
- ✅ 新增方法兼容性检查

### 建议的额外验证(需要运行环境)

- ⏳ 在 Hermes 0.21.4 环境下运行完整测试套件
- ⏳ 执行集成测试(基础对话、会话切换、Undo、Shutdown)
- ⏳ 验证 Gateway 身份解析
- ⏳ 验证 completed-turn context 行为

**注意**: 这些测试需要 Hermes 0.21.4 运行环境(通过 Desktop app 或源码安装)。当前环境使用的是 Hermes 0.18 (v2026.7.20)。

## 结论

**当前插件(v0.6.1)与 Hermes 0.21.4 完全兼容**,无需代码变更。建议更新文档声明以反映这一点。

**兼容性评级**: ✅ **Fully Compatible**

---

**分析基于**:
- Hermes 源码:v2026.9.21 (GitHub tag)
- 插件源码:v0.6.1 (当前工作目录)
- 分析方法:静态代码分析 + 接口对比
