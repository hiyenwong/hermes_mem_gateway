[文档首页](README.md) > 数据模型

# 数据模型

## ProviderConfig

> 提供者配置对象，定义记忆工作空间、权限策略和索引参数。

```python
@dataclass
class ProviderConfig:
    memory_workspace: str = "default"
    profile_id: str = "default"
    allow_non_primary_durable_writes: bool = False
    shared_writer_emails: list[str] = field(default_factory=list)
    shared_explicit_required: bool = True
    promotion_min_score: float = 0.8
    recall_limit_per_layer: int = 4
    embedding_dimensions: int = 64
    gateway_platforms: list[str] = field(
        default_factory=lambda: ["gateway", "discord", "slack", "telegram", "whatsapp"]
    )
    storage_root: str = ""
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `memory_workspace` | `str` | — | 工作空间命名空间，用于 durable memory 分区 |
| `profile_id` | `str` | — | 配置分区标识，决定存储路径 |
| `allow_non_primary_durable_writes` | `bool` | — | 允许非主上下文写入持久记忆（默认 False） |
| `shared_writer_emails` | `list[str]` | — | 允许写入 shared memory 的 Gateway 用户邮箱白名单 |
| `shared_explicit_required` | `bool` | — | 要求显式 shared intent 才能写入 shared memory（默认 True） |
| `promotion_min_score` | `float` | — | 记忆升级最低置信度阈值（默认 0.8） |
| `recall_limit_per_layer` | `int` | — | 每层召回记录数上限（默认 4） |
| `embedding_dimensions` | `int` | — | 语义向量维度（默认 64） |
| `gateway_platforms` | `list[str]` | — | Gateway 平台标识列表，用于用户身份判断 |
| `storage_root` | `str` | — | 自定义存储根路径（空时使用 hermes_home） |

**关联**：[Config 模块](modules/config.md)、[API 参考](api.md#load_config)

---

## RuntimeContext

> 运行时上下文，描述当前会话的平台、智能体身份和用户信息。

```python
@dataclass
class RuntimeContext:
    session_id: str
    platform: str = "cli"
    agent_context: str = "primary"
    agent_identity: str = "default"
    agent_workspace: str = ""
    parent_session_id: str = ""
    user_id: str = ""
    user_email: str = ""
    user_name: str = ""
    principal_source: str = ""
    request_metadata: dict[str, Any] | None = None
    metadata_shared_intent: bool | None = None
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | `str` | ✓ | 当前会话标识符 |
| `platform` | `str` | — | 平台标识（"cli"、"gateway"、"discord" 等） |
| `agent_context` | `str` | — | 上下文类型（"primary" 或 "subagent"） |
| `agent_identity` | `str` | — | 智能体身份标识 |
| `agent_workspace` | `str` | — | 工作空间标识 |
| `user_id` | `str` | — | 用户 ID（用于 Gateway 用户身份） |
| `user_email` | `str` | — | 用户邮箱（用于 Gateway 用户身份） |
| `user_name` | `str` | — | 用户显示名称 |
| `metadata_shared_intent` | `bool | None` | — | 从请求元数据解析的 shared intent 标记 |

**关联**：[Namespace 模块](modules/namespace.md)

---

## NamespaceContext

> 命名空间上下文，描述记忆存储的分区键和权限状态。

```python
@dataclass
class NamespaceContext:
    profile_id: str
    workspace_id: str
    principal_id: str
    session_id: str
    platform: str
    agent_context: str
    is_gateway: bool
    durable_user_allowed: bool
    durable_shared_allowed: bool
    user_id: str
    user_email: str
    user_name: str
    principal_source: str
    request_metadata: dict[str, Any]
    metadata_shared_intent: bool | None
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `principal_id` | `str` | ✓ | 记忆主体标识（Gateway 用户为 user_email/user_id，否则为 `__shared__`） |
| `is_gateway` | `bool` | ✓ | 是否为 Gateway 平台用户 |
| `durable_user_allowed` | `bool` | ✓ | 是否允许写入 semantic_user 层 |
| `durable_shared_allowed` | `bool` | ✓ | 是否允许写入 semantic_shared 层 |
| `principal_source` | `str` | — | principal_id 来源（"user_email"、"user_id" 或空） |

**属性**：`can_write_durable` — 组合判断是否可写持久记忆

**关联**：[Namespace 模块](modules/namespace.md)

---

## CandidateMemory

> 记忆候选对象，描述待升级的记忆内容及其置信度。

```python
@dataclass
class CandidateMemory:
    content: str
    kind: str
    confidence: float
    fingerprint: str
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | `str` | ✓ | 记忆内容文本 |
| `kind` | `str` | ✓ | 记忆类型（"explicit_memory"、"possible_fact"） |
| `confidence` | `float` | ✓ | 置信度分数（0.0–1.0） |
| `fingerprint` | `str` | ✓ | 内容指纹（SHA1 哈希，用于去重） |

**关联**：[Governance 模块](modules/governance.md)

---

## SearchResult

> 语义检索结果，包含记忆记录和相关性分数。

```python
@dataclass
class SearchResult:
    record: dict[str, Any]
    score: float
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `record` | `dict[str, Any]` | ✓ | 记忆记录字典（来自 SQLite） |
| `score` | `float` | ✓ | 语义相似度分数 |

**关联**：[Storage 模块](modules/storage.md)

---

## Validation Result

> 存储验证结果字典结构。

```python
{
    "sqlite_exists": bool,
    "memory_count": int,
    "index_backend": str,  # "lancedb" 或 "stub"
    "index_path": str,
}
```

**关联**：[API 参考](api.md#validate_storage)

---

## 参见

- [API 参考](api.md)
- [架构说明](architecture.md)