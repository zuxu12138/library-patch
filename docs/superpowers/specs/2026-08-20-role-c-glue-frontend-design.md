# C 角色（粘合侧：功能 + 前端）实现设计

> 状态：已与人类伙伴确认，进入实现阶段。
> 范围：仅覆盖 `docs/分工.md` 中 **C · 粘合侧** 名下文件。不改动 `service/`、`agent/core/`、`agent/memory/`（A/B 地盘）。
> 契约来源：`docs/接口契约.md`（① Java REST 字段、② AgentLoop 签名 + MemoryEntry、③ trace_id 传递）。契约文字为准，本文档不重复定义、只描述如何消费。

## 1. 背景与约束

当前仓库里 `service/`、`agent/core/`、`agent/memory/` 均只有 `.gitkeep`，A、B 尚未交付实现。C 的代码必须：

- 按契约真实路径引用 A/B 的模块（例如 `from agent.core.agent_loop import AgentLoop`），不在 A/B 目录下放任何占位/影子实现。
- 在 A/B 交付前，通过依赖注入 + 测试替身，让 C 自己名下的业务逻辑可独立编写、独立测试。
- `main.py` 的"能否启动"如实反映 A/B 的交付进度——B 交付前 `main.py` 因 `ImportError` 无法启动是预期状态，不伪造可运行的假象。

## 2. 模块地图

```
web/ (Vue3+Vite+ECharts, :5173)
  │  只调 agent 的 REST，不直连 Java，不直连第三方数据源
  ▼
agent/main.py (FastAPI, :8000)
  ├─ /findbook/*      → features/findbook/service.py       → AgentLoop → service_client → Java
  ├─ /knowledge/*     → features/knowledge_map/service.py  → S2 客户端 / AgentLoop(摘要用LLM)
  ├─ /seat/*          → features/seat_predict/service.py   → 采集库SQLite(基线) + service_client(兜底)
  ├─ /memory/feedback → 直调 AgentLoop.record_feedback（通用反馈兜底入口）
  └─ /health          → 聚合自身 + 透传 Java /api/health
```

## 3. 契约替身（Mock）策略

不在 `agent/core/`、`agent/memory/`、`service/` 下放任何占位文件。替身只存在于 `agent/tests/` 下，C 自己名下：

1. **对 Java 层（契约①）**：`service_client.py` 用 `httpx.AsyncClient` 做真实调用；测试用 `httpx.MockTransport`（httpx 自带）伪造 Java 响应，覆盖正常/业务错误/超时/429退避/4xx不重试五种场景。
2. **对 AgentLoop（契约②）**：`findbook/service.py`、`knowledge_map/service.py`、`seat_predict/service.py` 均通过构造函数注入 `agent_loop` 实例，不在模块顶层导入全局单例。`agent/tests/` 下写 `FakeAgentLoop`（与 `AgentLoop.run` / `record_feedback` 签名、`AgentResult` 字段完全一致的假类），注入进被测 service 类做单元测试。
3. `main.py` 中的真实装配代码始终 `from agent.core.agent_loop import AgentLoop`，B 交付前该行 `ImportError` 是预期状态，不规避。

## 4. `agent/service_client.py` —— 调 Java 层（契约①消费方）

```python
class ServiceError(Exception):
    """Java 侧返回业务错误码 (code != 0)。"""
    def __init__(self, code: int, msg: str): ...

class ServiceUnavailable(Exception):
    """网络/超时/重试耗尽后的最终不可用状态。"""

class ServiceClient:
    def __init__(self, base_url: str, timeout: float = 5.0, internal_token: str | None = None):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._token = internal_token

    async def search_books(self, query: str, page: int, page_size: int, trace_id: str) -> dict: ...
    async def seats_now(self, trace_id: str) -> dict: ...
    async def health(self, trace_id: str) -> dict: ...

    async def aclose(self) -> None: ...
```

行为规则：

- 每次请求头带 `X-Trace-Id: <trace_id>`（透传调用方传入值，不在此生成；trace_id 生成是 B 在 `agent_loop.py` 里的职责）。若构造时传入 `internal_token`，额外带 `X-Internal-Token`。
- 响应按信封 `{code, msg, data}` 解包：`code == 0` 返回 `data`；`code != 0` 抛 `ServiceError(code, msg)`。
- 容错分层（对应横切关注点①C 的一半）：
  - 超时 / HTTP 5xx / HTTP 429 → 重试，指数退避（基础 0.5s，×2，最多 2 次重试，共 3 次尝试）
  - HTTP 4xx（除 429）→ 不重试，直接抛 `ServiceError`（或专门的 `ServiceClientError` 表示请求本身有问题）
  - 重试全部耗尽 → 抛 `ServiceUnavailable`
- 不在此类里做"Java 挂了直读采集库"的降级——那是 `seat_predict/service.py` 的职责，本类只如实报告不可用。
- `search_books`/`seats_now` 返回值就是契约①里定义的 `data` 结构，不做二次改名或裁剪。

## 5. `agent/features/findbook/service.py` —— P0 找书

```python
class FindBookService:
    def __init__(self, agent_loop: AgentLoop, service_client: ServiceClient):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._agent_loop.register_tool("search_books", self._search_books_tool)

    async def _search_books_tool(self, query: str, page: int, page_size: int, trace_id: str) -> dict:
        try:
            return await self._service_client.search_books(query, page, page_size, trace_id)
        except (ServiceError, ServiceUnavailable):
            return {"error": "图书检索服务暂时不可用，请稍后再试"}

    async def find(self, query: str, page: int, page_size: int, user_id: str, trace_id: str) -> AgentResult:
        return await self._agent_loop.run(
            feature="findbook", subject="找书",
            task=f"查询: {query}",
            tool_name="search_books",
            tool_args={"query": query, "page": page, "page_size": page_size, "trace_id": trace_id},
            user_id=user_id, trace_id=trace_id,
            query_key="query",
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback, user_id=user_id,
            task_context=f"找书:{feedback[:30]}", trace_id=trace_id,
        )
```

工具函数捕获 `service_client` 的异常，转成明确的错误 payload，不让异常穿透整个 agent 循环变成裸 500。`AgentResult.output` 直接是契约①的书目结构，不二次加工。

## 6. `agent/features/knowledge_map/` —— P1 知识地图（☆扩展）

**`semantic_scholar.py`**：

```python
class SemanticScholarClient:
    def __init__(self, base_url: str = "https://api.semanticscholar.org/graph/v1", timeout: float = 10.0): ...
    async def search(self, query: str, limit: int = 10) -> list[dict]: ...
    async def paper(self, paper_id: str) -> dict: ...
    async def references(self, paper_id: str, limit: int = 20) -> list[dict]: ...  # 展平 data[].citedPaper
```

429 时指数退避（基础 1s，×2，最多 3 次重试）。

**`s2_cache.py`**（横切关注点②C 的一半：S2 持久缓存，降低 429）：

```python
class S2Cache:
    def __init__(self, path: str = "agent/features/knowledge_map/.s2_cache.json"): ...
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict) -> None: ...
```

JSON 文件缓存，key = `f"{endpoint}:{paper_id_or_query}"`。`SemanticScholarClient` 的调用方（`service.py`）在调用前查缓存、调用后写缓存，缓存类本身不知道 HTTP 细节。

**`service.py`**：

```python
class KnowledgeMapService:
    def __init__(self, agent_loop: AgentLoop, s2_client: SemanticScholarClient, s2_cache: S2Cache):
        self._agent_loop = agent_loop
        self._s2 = s2_client
        self._cache = s2_cache
        self._agent_loop.register_tool("build_citation_graph", self._build_graph_tool)
        self._agent_loop.register_tool("summarize_paper", self._summarize_tool)

    async def _build_graph_tool(self, paper_id: str, trace_id: str) -> dict:
        # 查缓存 → 未命中调 self._s2.references → 写缓存 → 组装 {nodes, edges}
        ...

    async def _summarize_tool(self, paper_id: str, trace_id: str) -> dict:
        # 查缓存拿 paper 详情 → 交给 LLM（agent_loop 内部处理，此工具只返回原始 paper 数据供 planner 用）
        ...

    async def build_graph(self, paper_id: str, user_id: str, trace_id: str) -> AgentResult:
        return await self._agent_loop.run(
            feature="knowledge_map", subject="知识地图",
            task=f"构建引用图: {paper_id}",
            tool_name="build_citation_graph",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id, trace_id=trace_id,
            query_key=None,  # 不是检索词精炼场景
        )

    async def summarize(self, paper_id: str, user_id: str, trace_id: str) -> AgentResult:
        return await self._agent_loop.run(
            feature="knowledge_map", subject="知识地图",
            task=f"摘要: {paper_id}",
            tool_name="summarize_paper",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id, trace_id=trace_id,
            query_key=None,
        )
```

## 7. `agent/features/seat_predict/service.py` —— P2 座位预测（○可选，笨基线）

```python
class SeatPredictService:
    def __init__(self, agent_loop: AgentLoop, service_client: ServiceClient, seats_db_path: str):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._db_path = seats_db_path
        self._agent_loop.register_tool("predict_seats", self._predict_tool)

    def _read_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _predict_tool(self, weekday: int, hour: int, trace_id: str) -> dict:
        # 1. 只读连接查历史同 weekday+同时段平均占用率，按升序排序（笨基线：同层同时段历史平均）
        # 2. 尝试 service_client.seats_now() 做实时校正；ServiceUnavailable 时忽略，仅用历史基线
        ...

    async def predict(self, weekday: int, hour: int, user_id: str, trace_id: str) -> AgentResult:
        return await self._agent_loop.run(
            feature="seat_predict", subject="座位预测",
            task=f"预测: weekday={weekday} hour={hour}",
            tool_name="predict_seats",
            tool_args={"weekday": weekday, "hour": hour, "trace_id": trace_id},
            user_id=user_id, trace_id=trace_id,
            query_key=None,
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback, user_id=user_id,
            task_context=f"座位纠错:{feedback[:30]}", trace_id=trace_id,
        )
```

读连接只读，不建表、不设 WAL——建库/WAL 是采集器（A）的职责（横切关注点④）。

## 8. `agent/benchmark/harness.py` —— 04 赛道指标面板（☆）

```python
@dataclass
class TaskMetric:
    task_name: str
    elapsed_ms: float
    tokens: int
    memory_hit: bool       # len(memories_used) > 0
    used_llm: bool

class BenchmarkHarness:
    def __init__(self, findbook_service: FindBookService):
        self._findbook = findbook_service
        self._metrics: list[TaskMetric] = []

    async def run_task(self, query: str, user_id: str, trace_id: str) -> TaskMetric: ...
    async def run_batch(self, queries: list[str], user_id: str = "benchmark") -> list[TaskMetric]: ...
    def report(self) -> dict:
        # 聚合：平均延迟、总token、记忆命中率 = hit数/总数
        ...
    def to_markdown(self) -> str: ...
```

先搭框架跑通结构，指标数字依赖真实 LLM key 才有意义，留空跑批即可。记忆误用率需人工标注负反馈样本，本轮不做自动化，只留字段占位在报告里注明"待人工标注"。

## 9. `web/` 前端 —— Vue 3 + Vite + ECharts

```
web/
├── index.html
├── vite.config.ts
├── package.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts
│   ├── api/
│   │   ├── client.ts        axios 封装：baseURL=agent(:8000)，统一注入 X-User-Id
│   │   │                    （从 localStorage 读，缺省写入 "default"）；不生成/不传 X-Trace-Id
│   │   │                    （由 agent 侧兜底生成，前端保持简单）；响应/错误码→人话文案映射表
│   │   ├── findbook.ts      search(query, page, pageSize) / feedback(text)
│   │   ├── knowledge.ts     buildGraph(paperId) / summarize(paperId) / searchPapers(query)
│   │   └── seat.ts          predict(weekday, hour) / feedback(text)
│   ├── views/
│   │   ├── FindBookView.vue      搜索框 + 结果卡片(索书号/架位/在馆状态) + FeedbackBox
│   │   ├── KnowledgeMapView.vue  论文搜索 + ECharts 力导向关系图 + 摘要面板 + FeedbackBox
│   │   └── SeatPredictView.vue   星期/时段选择 + ECharts 占用率条形图 + FeedbackBox
│   └── components/
│       ├── FeedbackBox.vue   👍/👎 + 文字反馈，统一调 /memory/feedback（或各功能自己的 feedback 路由）
│       ├── LoadingState.vue
│       └── ErrorState.vue    展示 client.ts 里映射后的人话错误文案
```

错误文案映射表（`client.ts` 内维护，示例）：

| code 段位 | 前端文案 |
|---|---|
| 50001/50002 | "图书馆数据服务暂时不可用，请稍后再试" |
| 60001 | "AI 助手暂时无法使用，已为你展示基础结果" |
| 60002 | "偏好记忆服务异常，本次结果可能未个性化" |
| 其它非0 | "出了点问题，请稍后再试"（兜底文案，不裸露 code） |

## 10. `agent/main.py` + 共享文件

路由清单（全部经统一 `envelope()` helper 包成 `{code, msg, data}`，全局异常处理器兜底捕获未预期异常转成 60xxx 错误码）：

```
POST /findbook/search        FindBookService.find
POST /findbook/feedback      FindBookService.feedback
POST /knowledge/graph        KnowledgeMapService.build_graph
POST /knowledge/summarize    KnowledgeMapService.summarize
POST /seat/predict           SeatPredictService.predict
POST /seat/feedback          SeatPredictService.feedback
POST /memory/feedback        AgentLoop.record_feedback 兜底通用入口
GET  /health                 聚合自身状态 + 透传 service_client.health()
```

启动装配（`lifespan` 或模块级单例）：

```python
from agent.core.agent_loop import AgentLoop   # B 未交付前 ImportError，属预期状态
from agent.memory import ...                  # 若 AgentLoop 内部自行装配 memory，此处无需直接引用

agent_loop = AgentLoop()
service_client = ServiceClient(base_url=config.SERVICE_BASE_URL, internal_token=config.INTERNAL_TOKEN)
findbook_service = FindBookService(agent_loop, service_client)
knowledge_service = KnowledgeMapService(agent_loop, SemanticScholarClient(), S2Cache())
seat_service = SeatPredictService(agent_loop, service_client, seats_db_path=config.SEATS_DB_PATH)
```

所有路由从请求头读 `X-User-Id`（缺省 `"default"`）、`X-Trace-Id`（缺省交给 `agent_loop` 内部生成——路由层不生成）。

**共享文件**（C 主维护，给 A/B 留追加空间，遵循"只追加不删"）：

- `agent/requirements.txt`：`fastapi`、`uvicorn[standard]`、`httpx`、`pydantic`、`pytest`、`pytest-asyncio`，文件末尾留注释 `# B: 请在此追加 openai SDK 等依赖，只追加不要删除已有行`
- `agent/config.py`：`SERVICE_BASE_URL`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`INTERNAL_TOKEN`、`SEATS_DB_PATH`，全部 `os.getenv` 读取并给合理默认值，缺失环境变量不应导致导入期报错
- `agent/.env.example`：对应每个变量的占位模板 + 注释
- `agent/pytest.ini`：`[pytest]` + `asyncio_mode = auto`

## 11. 测试策略

- `agent/tests/fakes.py`（新增，C 名下）：`FakeAgentLoop`（签名/字段严格对齐契约②）、httpx `MockTransport` 工厂函数，供其余测试文件复用。
- `agent/tests/test_service_client.py`：五种场景（成功/业务错误/超时/429退避成功/4xx不重试）。
- `agent/tests/test_findbook_service.py`：用 `FakeAgentLoop` 验证 `find`/`feedback` 参数组装正确、工具函数对 `ServiceUnavailable` 的降级行为。
- `agent/tests/test_knowledge_map_service.py`：S2 客户端用 mock transport 测 429 退避 + 展平逻辑；`S2Cache` 读写测试；service 层用 `FakeAgentLoop`。
- `agent/tests/test_seat_predict.py`（分工表里已列出的 ★ 待建文件）：占用率排序正确性、`busy_timeout` 设置、Java 不可用时忽略实时校正仅用基线。
- `agent/benchmark/` 不强制单测，跑批脚本手动验证结构正确即可。
- `web/`：本轮不引入前端单测框架（YAGNI，赛期优先端到端可用性），用手动跑 `npm run dev` + 联调验证；如后续需要再补 Vitest。

## 12. 明确不做（YAGNI，本轮范围外）

- 不实现前端登录/用户系统，`X-User-Id` 固定走 `localStorage` 存的 `"default"` 或用户手动输入的字符串。
- 不给前端加状态管理库（Pinia等），三个页面独立、无需跨页共享状态，用组件内 `ref`/`reactive` 即可。
- 不做 S2 客户端的持久化跨进程锁；JSON 文件缓存并发写冲突在赛期数据量下不构成风险，不做额外处理。
- 不在本轮实现鉴权 token 的前端交互（`X-Internal-Token` 只在部署公网时启用，走环境变量，前端无需感知）。
