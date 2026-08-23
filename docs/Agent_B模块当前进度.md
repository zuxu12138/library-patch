# Agent 项目 B 模块当前进度说明

## 1. 模块定位

本项目采用“按层横切”的三人分工方式。本人负责 **B · 大脑侧（Python 内核）**，核心职责是：

> 负责 Agent 的记忆、检索、规划与反馈闭环，使 Agent 能够基于用户历史信息持续优化后续响应。

B 模块是整个 Agent 的智能内核，主要关注 **Memory → Retrieval → Planning → Feedback** 的闭环能力。

---

## 2. 负责文件

### 2.1 Agent Core

```text
agent/core/
├── llm.py
├── planner.py
└── agent_loop.py
```

- `llm.py`：统一封装 LLM 调用，并完成 token 使用量统计。
- `planner.py`：负责结合用户当前请求与历史记忆进行记忆精炼和规划。
- `agent_loop.py`：负责 Agent 主循环、`trace_id` 生成、反馈处理和反馈幂等控制。

### 2.2 Memory

```text
agent/memory/
├── models.py
├── store.py
├── retriever.py
└── extractor.py
```

- `models.py`：定义记忆数据结构 `MemoryEntry`。
- `store.py`：负责记忆存储、FTS5 全文检索、时间衰减和冲突降权。
- `retriever.py`：根据当前任务检索最相关的历史记忆。
- `extractor.py`：利用 LLM 从对话或反馈中抽取结构化记忆，并通过 JSON mode 与 Pydantic 完成格式校验。

### 2.3 Tests

```text
agent/tests/
├── test_memory.py
└── test_planner.py
```

- `test_memory.py`：测试记忆写入、去重、用户隔离、衰减、冲突处理和检索逻辑。
- `test_planner.py`：测试 Planner 对相关记忆的使用、无记忆场景和异常场景下的稳定性。

---

## 3. 当前已完成进度

目前已完成 B 模块的整体职责梳理和技术方案设计，主要包括以下内容。

### 3.1 完成 B 模块边界确认

已经明确 B 模块只负责 Agent 智能内核，不直接负责 Java 数据服务、前端页面和具体业务功能。

当前职责边界为：

```text
A：数据进入
B：记忆与智能内核
C：业务功能与产品整合
```

B 模块不会直接修改 A、C 名下文件，避免多人开发过程中的代码冲突。

### 3.2 完成 Agent 记忆闭环设计

当前确定的基本闭环为：

```text
用户请求
   ↓
检索历史记忆
   ↓
记忆精炼
   ↓
Planner 结合记忆进行规划
   ↓
Agent 执行
   ↓
用户反馈 / 新信息
   ↓
Extractor 提取结构化记忆
   ↓
去重、冲突处理、写入 Memory Store
   ↓
后续请求继续使用
```

目标是使 Agent 不仅能够完成单轮任务，还能够根据用户历史偏好和反馈持续改进。

### 3.3 完成 MemoryEntry 字段初步设计

当前已经明确 `MemoryEntry` 至少需要重点考虑：

- `user_id`：标识记忆所属用户，避免不同用户之间发生记忆串用。
- `content`：记忆的实际内容。
- `dedup_hash`：用于记忆去重，防止同一信息被重复写入。
- `created_at`：记忆创建时间。
- `updated_at`：记忆最近更新时间。
- `importance`：记忆的重要程度。
- `confidence`：系统对该记忆可靠程度的判断。

最终字段仍需与 C 模块确认接口契约后固定。

### 3.4 完成记忆存储策略设计

`store.py` 当前确定包含三个核心机制：

#### FTS5 全文检索

使用 SQLite FTS5 对历史记忆进行文本检索，为 Retriever 提供候选记忆。

#### 时间衰减

较旧的记忆随着时间推移降低权重，使近期信息更容易被优先使用。

#### 冲突降权

当新旧记忆发生冲突时，不直接删除旧记忆，而是降低旧记忆权重，使较新的信息获得更高优先级。

### 3.5 完成记忆去重思路设计

计划通过 `dedup_hash` 对结构化记忆进行去重。

例如：

```text
“我喜欢靠窗座位”
“我还是更喜欢坐靠窗的位置”
```

在标准化后尽量识别为同类记忆，避免重复写入数据库。

### 3.6 完成记忆抽取方案设计

`extractor.py` 计划采用：

```text
用户对话 / 用户反馈
        ↓
       LLM
        ↓
     JSON Mode
        ↓
 Pydantic Validation
        ↓
  Structured Memory
```

只有满足数据结构要求的结果才能进入记忆库，从而减少自由文本直接写入数据库带来的格式不一致问题。

### 3.7 完成 trace_id 机制设计

每次 Agent 请求由 `agent_loop.py` 生成唯一 `trace_id`。

```text
AgentLoop 生成 trace_id
        ↓
C 模块 service_client 注入 X-Trace-Id
        ↓
A 模块 Java 服务读取 trace_id
```

`trace_id` 用于串联一次 Agent 请求中的模型调用、业务接口调用和日志信息，方便后续调试与问题定位。

### 3.8 完成反馈幂等机制需求确认

`record_feedback(...)` 需要保证同一条反馈即使被重复提交，也不会被重复处理或重复写入记忆库。

该机制主要用于解决网络重试、前端重复提交等情况下产生重复记忆的问题。

---

## 4. 接口契约

B 模块与 C 模块需要重点固定以下接口：

```text
AgentLoop.run(...)
AgentLoop.record_feedback(...)
MemoryEntry
```

接口契约需要明确：

- 函数名称
- 参数名称
- 参数类型
- 返回值格式
- MemoryEntry 字段
- 错误处理方式

接口确定后，双方不得单方面修改；如需修改，需要同步调整调用方。

---

## 5. 下一步开发计划

下一阶段按照以下顺序推进：

```text
models.py
   ↓
store.py
   ↓
retriever.py
   ↓
extractor.py
   ↓
planner.py
   ↓
llm.py
   ↓
agent_loop.py
   ↓
test_memory.py / test_planner.py
```

具体计划：

1. 完成 `MemoryEntry` 数据模型，并与 C 模块固定接口契约。
2. 完成 SQLite + FTS5 的基础记忆存储和检索功能。
3. 实现 `dedup_hash` 去重机制。
4. 实现时间衰减与冲突降权逻辑。
5. 完成 Retriever 的相关记忆召回。
6. 完成 Extractor 的 JSON Mode + Pydantic 结构化记忆抽取。
7. 完成 Planner 的记忆精炼与上下文组装。
8. 完成统一 LLM 调用与 token 统计。
9. 将上述模块接入 `AgentLoop`，形成完整反馈记忆闭环。
10. 完成自动化测试并与 C 模块进行联调。

---

## 6. 测试计划

### test_memory.py

重点覆盖：

- 不同 `user_id` 之间的记忆隔离。
- 相同记忆重复写入时的去重。
- 新旧冲突记忆的权重变化。
- 旧记忆随时间的衰减。
- FTS5 是否能正确召回相关记忆。
- 空数据库和异常输入场景。

### test_planner.py

重点覆盖：

- Planner 是否正确利用相关历史记忆。
- 无相关记忆时能否正常工作。
- 无关记忆是否能被过滤。
- LLM 输出异常时的容错能力。

---

## 7. 当前阶段总结

目前 B 模块已经完成 **职责边界、整体架构、记忆闭环、记忆数据模型、存储策略、trace_id、反馈幂等和测试方向** 的初步设计。

下一步重点由“方案设计”进入“代码实现”，优先完成：

> **MemoryEntry → Memory Store → Retriever → Extractor**

在记忆底座稳定后，再完成 Planner 和 AgentLoop 的整体串联，最终形成一个能够根据用户历史和反馈持续优化的 Agent 智能内核。
