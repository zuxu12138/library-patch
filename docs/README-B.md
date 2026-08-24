# B 模块交接说明（大脑侧 · 反馈记忆内核）

> 作者：B。本文给 A/C 交代：B 交付了什么、C 怎么接、依赖有哪些、几个必须知道的内部决策。
> 契约 ② / ③ 的最终依据仍是 `../接口契约.md`，本文是落地版的单点参考。

---

## 1. 交付清单

```
agent/core/
├── llm.py          LLMClient + Usage(token 计量) + available + complete/complete_json
├── planner.py      Planner.plan()：记忆精炼查询；无 key/无记忆透传；异常降级
└── agent_loop.py   AgentLoop + AgentResult + register_tool + run + record_feedback(幂等) + trace 生成
agent/memory/
├── models.py       MemoryType 枚举 + MemoryEntry + dedup_key
├── store.py        MemoryStore(SQLite + FTS5) + add/query/resolve_conflicts/delete/delete_all
├── retriever.py    MemoryRetriever + retrieve + to_prompt_block
└── extractor.py    MemoryExtractor(JSON mode + pydantic 校验)
agent/tests/
├── test_memory.py  记忆内核测试（19 个）
└── test_planner.py 核心内核测试（16 个）
agent/__init__.py + core/ memory/ tests/ 各 __init__.py（空包标记，B 已建）
```

测试全绿：`python -m pytest agent/tests`（在仓库根目录跑）→ 35 passed。

---

## 2. 契约 ② —— C 调 B 的接口（定死，B 已按此实现）

### `AgentLoop.run(...)`（C 调它跑一次任务）

```python
async def run(
    self,
    feature: str,          # "findbook" / "knowledge_map" / "seat_predict"
    subject: str,          # 记忆主题, 如 "找书"
    task: str,             # 人类可读任务描述
    tool_name: str,        # 要调的工具名(先 register_tool)
    tool_args: dict,       # 工具参数
    user_id: str,          # 来自 X-User-Id
    trace_id: str,         # 来自 X-Trace-Id(可空,B 会新建)
    query_key: str | None = None,  # tool_args 里"检索词"的键, 给出则走记忆精炼
) -> AgentResult
```

### `AgentResult`（C 拿到后组装成信封 data）

```python
feature: str            # 功能名
output: Any             # 工具产出(如书目列表)
memories_used: list[str]  # 命中的记忆 id
elapsed_ms: float       # 耗时
tokens: int             # 本次 LLM token 消耗
plan_note: str          # 规划器给用户的说明(如"已按你的偏好只找近五年")
used_llm: bool          # 本次是否真调了 LLM
trace_id: str           # 回传, 便于日志串联
```

### `AgentLoop.record_feedback(...)`（C 把反馈入环）

```python
async def record_feedback(
    self,
    feedback: str,          # 用户反馈原文
    user_id: str,
    task_context: str = "", # 如 "找书:机器学习"
    trace_id: str = "",
) -> list[str]              # 返回新沉淀的记忆 id; 幂等: 重复反馈返回已存在的 id
```

### `MemoryEntry`（B 定义，C 只读不建）

字段与契约 ② 完全一致：`user_id / type / subject / content / applies_to="*" / confidence=0.8 / source="" / dedup_hash / entry_id / created_at / updated_at`。
> 注：`entry_id / dedup_hash / created_at / updated_at` 由 `store.add()` 自动填，构造时可不传（有默认值）。

---

## 3. C 怎么接（装配示例，main.py 里照抄即可）

```python
from agent.core.llm import LLMClient
from agent.core.planner import Planner
from agent.core.agent_loop import AgentLoop
from agent.memory.store import MemoryStore
from agent.memory.retriever import MemoryRetriever
from agent.memory.extractor import MemoryExtractor

llm = LLMClient(base_url=cfg.LLM_BASE_URL, api_key=cfg.LLM_API_KEY, model=cfg.LLM_MODEL)
store = MemoryStore(db_path="memory.db")          # 建议用绝对路径，配合 Litestream 备份
retriever = MemoryRetriever(store)
planner = Planner(llm)
extractor = MemoryExtractor(llm)
loop = AgentLoop(retriever=retriever, planner=planner, store=store, extractor=extractor)

loop.register_tool("search_books", search_books_handler)   # handler(args: dict)，可 async 可 sync

result = await loop.run(
    feature="findbook", subject="找书", task="找机器学习的书",
    tool_name="search_books", tool_args={"query": "机器学习"},
    user_id=user_id, trace_id=trace_id, query_key="query",
)
```

B 不直接 `import config`，全部走构造参数注入，C 负责从 `config.py` 读环境变量后传入。

---

## 4. 契约 ③ —— trace_id

- B 在 `run` / `record_feedback` 开头生成 **8 位 hex**（无则新建，有则透传）。
- C 在 `service_client.py` 调 Java 时把它塞进 `X-Trace-Id` 头；A 在 Java 过滤器读入放 MDC。

---

## 5. 依赖（B 新增，已写进 `requirements.txt` 的 B 段）

```
openai
pydantic>=2
pytest
pytest-asyncio<0.24   # 兼容 pytest 7.x
```

- C 请在 `requirements.txt` 下方**追加**自己的：`fastapi` / `uvicorn` / `httpx`。
- pytest 配置：B 用 `@pytest.mark.asyncio` 显式标记，**不依赖全局 pytest.ini**。若团队想统一 `asyncio_mode=auto`，三人一起在 `agent/pytest.ini` 定，别单方加。

---

## 6. 内部决策（C/A 不必改，知道即可）

| 点 | 决策 |
|---|---|
| 幂等去重 | `dedup_hash = sha1(user_id + 内容)`，memory 表唯一索引；`add()` 命中返回旧 id |
| 反馈级幂等 | `feedback_dedup` 表按 `sha1(user_id + 反馈)` 缓存已入库 id，重复反馈不再抽取 |
| 全文检索 | FTS5 **trigram**（中文子串友好）；<3 字查询自动回退 LIKE（功能不丢） |
| 时间衰减 | 半衰期 30 天（`MemoryStore(half_life_days=...)` 可调），得分 = 置信度 × 衰减 |
| 冲突降权 | 同类(user_id+type+subject)旧记忆 ×0.5（`resolve_conflicts`） |
| 适用范围 | `applies_to="*"` 通配，任意功能可见 |
| 抽取校验 | LLM 输出走 JSON mode + pydantic；校验失败重试一次，再失败丢弃（不污染记忆库） |

---

## 7. 我不碰的东西（避免越界）

`config.py` / `service_client.py` / `features/` / `main.py` / `benchmark/` / `web/` / Java 层 —— 归 A/C。共享文件（`requirements.txt` 等）我只追加自己的行。
