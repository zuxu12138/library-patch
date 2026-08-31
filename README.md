# 图书馆补丁 · 技术框架蓝图

> 一个 Agent + 一套反馈记忆 + 三个触角：**找书 (P0) · 知识地图 (P1) · 座位预测 (P2)**。

---

## 项目简介

**图书馆补丁** 是为大连理工大学图书馆打造的一站式智慧服务平台。它把过去需要跑好几个系统才能完成的事（找书、读论文、找座位）整合在一个 Agent 里，并通过一套反馈记忆系统让服务越用越懂你。

### 核心问题

传统图书馆服务存在几个痛点：OPAC 检索只能关键词匹配，找不到"相关推荐"；座位系统只显示当前状态，无法预测哪个区域下午有空；文献之间引用关系零散，无法直观展示知识脉络。这三个问题原本互不相干，但背后可以共用同一套记忆——你越用，它越懂你的阅读风格、座位偏好和检索习惯。

### 三大功能

| 优先级 | 功能 | 一句话描述 |
|---|---|---|
| **P0** | 找书 AI 馆员 | 模糊需求 → 澄清 → 检索 → 索书号/架位/在馆状态 + 相关推荐 |
| **P1** | 个人知识地图 | 文献 → 结构化摘要 → 引用关系图；反馈修正阅读风格 |
| **P2** | 座位预测 | 基于历史占用预测哪层适合你；用户纠错闭环修正 |

### 技术架构

系统采用**双栈分层**设计：

- **Python Agent 层**：产品大脑，负责意图理解、记忆检索、任务编排。使用 FastAPI 暴露 REST 接口，记忆存 SQLite（FTS5 全文检索），LLM 走 OpenAI 兼容协议。
- **Java 数据服务层**：数据闸门，把 OPAC 和座位系统等第三方脏接口封装成干净、稳定的内部 REST。使用 Spring Boot 3.3.5 + RestClient，OPAC 结果用 Caffeine 做 TTL 缓存。
- **采集器**：Python 纯标准库实现，定时从座位系统拉取区域级 + 单座级占用数据，存入 SQLite（WAL 模式），为 P2 预测提供历史时间序列。
- **前端**：Vue 3 + Vite + Tailwind v4 + ECharts，提供对话式找书、引用关系可视化、座位预测交互三个页面。

### 数据流

```
用户 → 前端(Vue) → Python Agent → Java 服务层 → 图书馆数据源 (OPAC / 座位系统)
                              ↓
                         反馈记忆系统 (SQLite + FTS5)
```

Agent 与 Java 层之间带内部 token 鉴权，所有请求携带 `X-Trace-Id` 贯穿两层日志，排查问题时可串联完整链路。

### 记忆机制

系统为三大功能（找书 / 知识地图 / 座位预测）提供统一的反馈记忆能力，形成"使用 → 反馈 → 记忆沉淀 → 下次使用更懂你"的闭环。记忆按 `user_id` 隔离，LLM 未配置时记忆功能静默降级，不影响主流程。

---

#### 记忆数据模型

每条记忆是一个 `MemoryEntry`，由 LLM 从用户反馈中抽取或直接记录：

| 字段 | 说明 |
|------|------|
| `entry_id` | UUID，主键 |
| `user_id` | 用户标识，实现多用户隔离 |
| `type` | 记忆类型：`preference`（偏好）/ `rule`（规则）/ `episode`（事件） |
| `subject` | 主题，如"找书""座位预测" |
| `content` | 记忆正文 |
| `applies_to` | 适用功能范围，`"*"` 表示通配所有功能 |
| `confidence` | 置信度 0~1，新记忆默认 0.8 |
| `dedup_hash` | 幂等键：`SHA1(user_id + "\x00" + content)`，同一用户相同内容只存一次 |
| `created_at` / `updated_at` | 时间戳，用于时间衰减排序 |

---

#### 反馈入环流程

用户提交反馈（如"我喜欢靠窗的位置""以后只看近五年的论文"）后，系统按以下步骤处理：

```
用户反馈
  │
  ▼
① 幂等去重
   计算 feedback_hash = SHA1(user_id + "\x00" + feedback)
   查 feedback_dedup 表 → 已存在则直接返回缓存的 entry_ids（防手快多点）
  │
  ▼
② LLM 抽取结构化记忆
   调用 MemoryExtractor.extract()：
   - 携带该用户最近 10 条已有记忆（供 LLM 判断矛盾）
   - LLM JSON mode + pydantic 校验，抽取 0~3 条 MemoryEntry
   - 若 LLM 未配置或校验两次均失败，返回 []（静默降级）
  │
  ▼
③ 写入记忆库
   调用 MemoryStore.add(entry)：
   - 按 dedup_hash 幂等：UNIQUE 索引冲突 → 返回已有 entry_id
   - 同时写入 memory_fts（FTS5 全文检索虚拟表）
  │
  ▼
④ 矛盾消解
   若 LLM 判定本次反馈与某条旧记忆直接矛盾（如"喜欢靠窗" vs "喜欢靠门"）：
   - 对矛盾旧记忆执行 adjust_confidence(entry_id, factor=0.5) 降权
   - 非直接矛盾（如"靠窗" vs "安静"）不互相干扰
  │
  ▼
⑤ 缓存反馈映射
   feedback_dedup[feedback_hash] = [新 entry_ids]
   下次相同反馈直接命中，不再重复 LLM 调用
```

---

#### 记忆存储结构

记忆数据存储在 SQLite 中，共三张表：

**`memory` 表** — 主表，存储所有记忆条目

```sql
CREATE TABLE memory (
    entry_id    TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    type        TEXT NOT NULL,
    subject     TEXT NOT NULL,
    content     TEXT NOT NULL,
    applies_to  TEXT NOT NULL DEFAULT '*',
    confidence  REAL NOT NULL DEFAULT 0.8,
    source      TEXT NOT NULL DEFAULT '',
    dedup_hash  TEXT NOT NULL UNIQUE,   -- 幂等去重键
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX idx_memory_user ON memory(user_id);
```

**`memory_fts` 表** — FTS5 trigram 全文检索虚拟表

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    entry_id UNINDEXED,
    subject,
    content,
    tokenize='trigram'  -- trigram 对中文子串检索友好，3 字及以上可命中
);
```

**`feedback_dedup` 表** — 反馈级幂等缓存

```sql
CREATE TABLE feedback_dedup (
    feedback_hash TEXT PRIMARY KEY,
    entry_ids     TEXT NOT NULL  -- JSON 数组，如 ["a1b2", "c3d4"]
);
```

**WAL 模式**：数据库启用 `PRAGMA journal_mode=WAL`，支持读写并发（采集器写入 + P2 预测读取共享数据库）。

---

#### 记忆检索机制

`MemoryRetriever.retrieve()` 按以下策略召回记忆：

**1. 多路召回**

- **FTS 相关性召回**：用 `query_text` 在 `memory_fts` 做 trigram 全文检索（≥3 字触发），命中的记忆优先进入结果。
- **范围/主题召回**：按 `applies_to`（功能范围）+ `subject`（主题）无条件召回该范围内所有记忆，补全 FTS 可能错杀的偏好类记忆（如"只看近五年"与当前查询词无字面重合）。

**2. 去重与过滤**

- 两路召回结果合并去重
- 过滤 `confidence < min_confidence`（默认 0.0）的记忆

**3. 时间衰减排序**

按 `confidence × time_decay(created_at, now)` 综合得分降序排列，取 `top_k`：

```
time_decay = 0.5 ^ (age / (half_life_days × 86400))
```

默认半衰期 `half_life_days = 30`，即 30 天前记忆的衰减因子为 0.5。这意味着"上周喜欢靠窗"不会永远压过"昨天喜欢靠门"。

**4. 渲染提示词**

`to_prompt_block()` 将命中的记忆格式化为紧凑提示词，供 LLM 精炼检索词：

```
【用户记忆】
- [preference/找书] 只看近五年的中文论文 (置信度 0.85)
- [preference/座位预测] 喜欢靠窗位置 (置信度 0.80)
```

---

#### 三大功能如何使用记忆

| 功能 | 记忆主题 | applies_to | 如何使用 |
|------|---------|------------|---------|
| **找书** | `"找书"` | `"findbook"` | 检索时注入用户偏好（如"只看近五年"），Planner 精炼检索词；反馈时抽取偏好/规则记忆 |
| **知识地图** | `"知识地图"` | `"knowledge_map"` | 检索时注入阅读偏好；反馈时抽取文献类型偏好、研究兴趣 |
| **座位预测** | `"座位预测"` | `"seat_predict"` | 检索时注入座位偏好（如"喜欢靠门"），Planner 可调整推荐逻辑；反馈时抽取偏好/规则记忆 |

---

#### LLM 可选配置

记忆功能依赖 LLM（记忆抽取 + 查询精炼），但**未配置时系统自动降级，不影响主流程**：

| 场景 | LLM 未配置时行为 |
|------|----------------|
| 反馈提交 | `MemoryExtractor.extract()` 直接返回 `[]`，反馈不入环，前端仍显示"反馈已收到" |
| 查询精炼 | `Planner.plan()` 直接原样透传检索词，`plan_note` 为空 |
| 找书 / 座位预测 | 基础功能完全正常，只是没有记忆增强 |
| 知识地图 | 搜索 / 图谱 / 摘要功能正常（摘要依赖 LLM，未配置时返回降级提示） |

配置方式：在 `.env` 中设置 `LLM_API_KEY`、`LLM_BASE_URL`（可选，默认 OpenAI 官方）、`LLM_MODEL`（默认 `gpt-4o-mini`）。参考 `agent/.env.example`。

### 适用场景

- **01 赛道（大工图书馆）**：端到端解决找书难、座位难、文献散三个真实痛点
- **02 赛道（图书馆补丁）**：在旧系统上打新补丁，最小侵入改造
- **04 赛道（反馈记忆）**：同一套记忆贯穿三个场景，token 成本 / 命中率 / 误用率可量化可演示
