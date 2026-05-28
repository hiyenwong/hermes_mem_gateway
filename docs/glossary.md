[文档首页](README.md) > 术语表

# 术语表

## Episodic Memory（情景记忆）

会话级记忆层，绑定到特定 session_id。存储对话回合内容，会话结束后保留但不再主动召回。用于当前对话上下文恢复。

**使用位置**：[Storage 模块](modules/storage.md)、[MemoryProvider 模块](modules/memory_provider.md)

---

## Semantic User Memory（语义用户记忆）

用户级持久记忆层，绑定到 principal_id（Gateway 用户的 user_email 或 user_id）。仅 Gateway 平台用户可写入，实现用户私有记忆隔离。

**使用位置**：[Namespace 模块](modules/namespace.md)、[Governance 模块](modules/governance.md)

---

## Semantic Shared Memory（语义共享记忆）

工作空间级持久记忆层，绑定到 principal_id=`__shared__`。所有用户可读取，写入受 shared_writer_emails 白名单和 shared_explicit_required 策略控制。

**使用位置**：[Namespace 模块](modules/namespace.md)、[Governance 模块](modules/governance.md)

---

## Principal ID（主体标识）

记忆存储的主体分区键。Gateway 用户为 user_email 或 user_id，非 Gateway 用户为固定值 `__shared__`。

**使用位置**：[Namespace 模块](modules/namespace.md)

---

## Gateway Platform（网关平台）

需要用户身份认证的平台（gateway、discord、slack、telegram、whatsapp）。Gateway 用户拥有独立的 semantic_user 层。

**使用位置**：[Config 模块](modules/config.md)、[Namespace 模块](modules/namespace.md)

---

## Promotion（记忆升级）

从 episodic 层自动提取高置信度内容并持久化到 semantic 层的过程。由 `classify_turn` 分析对话回合，经置信度阈值过滤后升级。

**使用位置**：[Governance 模块](modules/governance.md)

---

## Fingerprint（指纹）

记忆内容的 SHA1 哈希，用于检测重复记忆。相同内容的记忆共享相同指纹。

**使用位置**：[Governance 模块](modules/governance.md)

---

## Supersession（取代关系）

新记忆取代旧记忆的关系。当新记忆与旧记忆内容重叠度 ≥ 75% 且不完全相同时，旧记忆标记为 superseded，新记忆引用旧记忆 ID。

**使用位置**：[Governance 模块](modules/governance.md)、[Storage 模块](modules/storage.md)

---

## Reinforcement（强化）

记忆命中召回时增加 reinforcement_count 的过程。高频访问的记忆在召回排序中优先展示。

**使用位置**：[Storage 模块](modules/storage.md)

---

## LanceDB

向量数据库，用于语义索引检索。本插件可选依赖，不可用时回退到 JSON stub 索引。

**使用位置**：[Storage 模块](modules/storage.md)

---

## OpenWebUI Headers

OpenWebUI 平台传递用户身份的 HTTP 头信息（X-OpenWebUI-User-Email、X-OpenWebUI-User-Id、X-OpenWebUI-User-Name）。

**使用位置**：[Namespace 模块](modules/namespace.md)

---

## 参见

- [架构说明](architecture.md)
- [数据模型](data_models.md)