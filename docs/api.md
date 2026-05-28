[文档首页](README.md) > API 参考

# API 参考

> 本插件对 Hermes 框架导出的公开接口。

## LayeredLanceDBSQLiteMemoryProvider

> 源码位置：[`modules/memory_provider.md`](modules/memory_provider.md)

### `initialize(session_id: str, **kwargs) -> None`

初始化提供者实例，加载配置、解析命名空间、启动存储层。

**参数**

| 名称 | 类型 | 说明 |
|------|------|------|
| `session_id` | `str` | 当前会话标识符 |
| `hermes_home` | `str` | Hermes home 目录路径（通过 kwargs 传入） |
| `agent_identity` | `str` | 智能体身份标识（可选，默认取配置 profile_id） |
| `agent_workspace` | `str` | 工作空间标识（可选，默认取配置 memory_workspace） |
| `platform` | `str` | 平台标识（可选，默认 "cli"） |
| `agent_context` | `str` | 上下文类型（可选，"primary" 或 "subagent"） |
| `user_id` | `str` | 用户标识（可选，用于 Gateway 用户身份） |
| `user_email` | `str` | 用户邮箱（可选，用于 Gateway 用户身份） |
| `headers` | `dict[str, str]` | OpenWebUI 头信息（可选，提取用户身份） |

**异常**：`RuntimeError` — 存储层初始化失败

**示例**

```python
provider.initialize(
    "session-1",
    hermes_home="/path/to/hermes",
    agent_identity="coder",
    platform="gateway",
    user_email="user@example.com",
)
```

---

### `prefetch(query: str, *, session_id: str = "") -> str`

预取召回上下文，从三层记忆中检索相关内容。

**参数**

| 名称 | 类型 | 说明 |
|------|------|------|
| `query` | `str` | 查询文本 |
| `session_id` | `str` | 会话标识（可选，默认使用当前会话） |

**返回值**：`str` — 格式化的召回上下文块，包含 `<memory-context>` 标签包裹的记忆内容

**示例**

```python
recall = provider.prefetch("coffee preferences")
# 返回：
# <memory-context>
# User semantic memory:
# 1. Remember that I prefer dark roast coffee beans.
# </memory-context>
```

---

### `sync_turn(user: str, assistant: str, *, session_id: str = "") -> None`

同步对话回合，插入 episodic 记录并异步触发记忆升级。

**参数**

| 名称 | 类型 | 说明 |
|------|------|------|
| `user` | `str` | 用户输入文本 |
| `assistant` | `str` | 智能体回复文本 |
| `session_id` | `str` | 会话标识（可选，默认使用当前会话） |

**示例**

```python
provider.sync_turn("Remember my name is Alice.", "Noted, Alice.")
```

---

### `on_session_switch(new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs) -> None`

处理会话切换，更新运行时上下文和命名空间。

**参数**

| 名称 | 类型 | 说明 |
|------|------|------|
| `new_session_id` | `str` | 新会话标识 |
| `parent_session_id` | `str` | 父会话标识（可选） |
| `reset` | `bool` | 是否清除旧会话的预取缓存（默认 False） |
| `kwargs` | `dict` | 其他运行时参数（platform, user_id 等） |

**示例**

```python
provider.on_session_switch(
    "session-2",
    reset=True,
    platform="gateway",
    user_id="user-1",
)
```

---

### `shutdown() -> None`

关闭提供者，等待异步任务完成并释放存储资源。

**示例**

```python
provider.shutdown()
```

---

### `validate_storage() -> dict[str, Any]`

验证存储状态，返回 SQLite 和索引信息。

**返回值**：[`dict[str, Any]`](data_models.md#validation-result) — 包含 sqlite_exists、memory_count、index_backend 等字段

**示例**

```python
result = provider.validate_storage()
# {"sqlite_exists": true, "memory_count": 42, "index_backend": "lancedb"}
```

---

### `rebuild_index() -> int`

重建语义索引，从 SQLite 重新加载所有语义层记忆。

**返回值**：`int` — 重建的索引记录数量

**示例**

```python
count = provider.rebuild_index()
print(f"Rebuilt {count} semantic memories")
```

---

## 配置管理函数

> 源码位置：[`modules/config.md`](modules/config.md)

### `load_config(hermes_home: str) -> ProviderConfig`

从 YAML 配置文件加载配置。

**返回值**：[`ProviderConfig`](data_models.md#providerconfig) — 配置对象

---

### `save_config(values: dict[str, Any], hermes_home: str) -> Path`

保存配置到 YAML 文件。

**返回值**：`Path` — 配置文件路径

---

## 治理策略函数

> 源码位置：[`modules/governance.md`](modules/governance.md)

### `classify_turn(user_text: str, assistant_text: str) -> list[CandidateMemory]`

分析对话回合，识别潜在记忆候选。

**返回值**：[`list[CandidateMemory]`](data_models.md#candidatememory) — 记忆候选列表

---

### `fingerprint_text(text: str) -> str`

计算文本指纹（SHA1 哈希），用于去重。

**返回值**：`str` — 40 字符十六进制指纹

---

## 参见

- [数据模型](data_models.md)
- [架构说明](architecture.md)
- [开发指南](developer_guide.md)