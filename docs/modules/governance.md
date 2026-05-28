上级：[架构说明](../architecture.md) | [文档首页](../README.md)

# Governance 模块

> 候选治理模块，负责记忆分类、指纹、排序和取代关系检测。

## 概述

Governance 模块定义候选记忆的启发式处理逻辑：

- **分类（classify_turn）** — 分析对话回合，识别显式记忆请求和潜在事实
- **去重检测（fingerprint_text）** — 计算内容指纹，检测重复记忆
- **取代检测（find_superseded）** — 检测内容重叠，标记旧记忆为已取代
- **排序评分（rank_record）** — 计算记忆的综合重要性分数

durable 写入授权、shared intent、目标层和 principal 选择由 [Policy](policy.md) 集中处理。

## 公开接口

| 符号 | 类型 | 说明 |
|------|------|------|
| [`CandidateMemory`](../data_models.md#candidatememory) | 类 | 记忆候选数据类 |
| [`classify_turn(user_text, assistant_text)`](../api.md#classify_turn) | 函数 | 分析对话回合，返回记忆候选列表 |
| [`fingerprint_text(text)`](../api.md#fingerprint_text) | 函数 | 计算文本指纹（SHA1） |
| `find_superseded(records, candidate)` | 函数 | 检测被取代的旧记忆 |
| `rank_record(base_score, ...)` | 函数 | 计算记忆排序分数 |

## 记忆分类规则

### 显式记忆（explicit_memory）

匹配正则表达式：
- `remember`、`memorize`
- `my preference is`、`i prefer`
- `my name is`、`call me`

置信度：**0.96**（高置信度，几乎总是升级）

### 潜在事实（possible_fact）

条件：
- 未匹配 transient 标记（today、tomorrow、right now、currently、temporary）
- 内容长度 ≥ 6 个单词

置信度：**0.52**（低置信度，需额外判断）

## 取代检测算法

当新记忆与旧记忆内容重叠度 ≥ 75%（Jaccard 相似度）且内容不完全相同时，旧记忆标记为 superseded。

## 依赖关系

- 被依赖：Promotion Service、[MemoryProvider](memory_provider.md)

## 参见

- [API 参考](../api.md)
- [数据模型](../data_models.md#candidatememory)
- [术语表](../glossary.md#promotion)
