# C 角色（粘合侧：功能 + 前端）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 C 角色名下的全部文件——`agent/main.py`、`agent/service_client.py`、三个 `agent/features/*`、`agent/benchmark/harness.py`、共享文件（`requirements.txt`/`config.py`/`.env.example`/`pytest.ini`）、以及 `web/` 前端（Vue3+Vite+ECharts），让"找书"功能端到端可体验，且不越界改动 A（`service/`、`collector/`）与 B（`agent/core/`、`agent/memory/`）的文件。

**Architecture:** Python 侧用依赖注入解耦对 B 的 `AgentLoop`（契约②）依赖，测试用自建 `FakeAgentLoop` 替身；对 A 的 Java 层（契约①）用 `httpx.AsyncClient` + 测试用 `httpx.MockTransport` 替身。前端只调 agent 层 REST，不直连 Java/第三方。`main.py` 的真实装配代码照契约路径 import，B 未交付前预期 `ImportError`，不规避。

**Tech Stack:** Python 3.12 + FastAPI + httpx + pytest/pytest-asyncio；Vue 3 + Vite + TypeScript + ECharts + axios + vue-router。

**Spec:** `docs/superpowers/specs/2026-08-20-role-c-glue-frontend-design.md`

## Global Constraints

- 只创建/修改以下路径下的文件：`agent/main.py`、`agent/service_client.py`、`agent/config.py`、`agent/requirements.txt`、`agent/.env.example`、`agent/pytest.ini`、`agent/features/**`、`agent/benchmark/**`、`agent/tests/**`、`web/**`。绝不在 `service/`、`agent/core/`、`agent/memory/`、`collector/` 下创建任何文件（包括空的 `__init__.py`）。
- 所有 Python 测试命令均写作 `python -m pytest <path> -v`，且从仓库根目录执行（`python -m pytest` 会把当前工作目录插入 `sys.path`，使 `agent` 作为 namespace package 可被 `import agent.xxx` 直接导入，不需要 `__init__.py`，不修改 `sys.path`）。
- 所有 Java REST 响应、Agent 层响应统一信封 `{code, msg, data}`；错误码段位：`40001-40099` 请求错误、`50001-50099` Java 数据层、`60001-60099` Agent 层（`docs/接口契约.md`）。
- HTTP 头：`X-User-Id`（缺省 `"default"`）、`X-Trace-Id`（agent 侧缺省生成，8 位十六进制）、`X-Internal-Token`（仅公网部署时启用）。
- `service_client.py` 对 Java 的重试策略：超时/5xx/429 → 指数退避重试（基础 0.5s，×2，最多 2 次重试，共 3 次尝试）；4xx（除429）→ 不重试直接报错。
- `semantic_scholar.py` 对 S2 的重试策略：429 → 指数退避（基础 1s，×2，最多 3 次重试）。
- `seat_predict/service.py` 读 `seats.db` 用只读连接：`sqlite3.connect(path, timeout=5.0)` + `PRAGMA busy_timeout=5000`，不建表、不设 WAL（那是 A 的职责）。
- ⚠️ `seat_predict` 读取的表结构 (`seat_snapshots`，字段 `weekday`/`hour`/`area_name`/`occupied`/`total`) 是本计划的**假定 schema**，接口契约未定义此表，需与 A 确认；若实际字段不同，只需改 Task 8 里的一处 SQL。
- `requirements.txt`/`config.py`/`.env.example` 是共享文件，本计划只追加不删除，并在文件尾/适当位置留给 A/B 追加的注释标记。
- 前端不生成/不传 `X-Trace-Id`（由 agent 侧兜底生成，前端逻辑保持简单）；只传 `X-User-Id`。

---

## Task 1: 共享文件脚手架（requirements / config / .env.example / pytest.ini）

**Files:**
- Create: `agent/requirements.txt`
- Create: `agent/config.py`
- Create: `agent/.env.example`
- Create: `agent/pytest.ini`
- Test: `agent/tests/test_config.py`

**Interfaces:**
- Produces: `agent.config` 模块级常量 `SERVICE_BASE_URL: str`、`LLM_BASE_URL: str`、`LLM_API_KEY: str`、`LLM_MODEL: str`、`INTERNAL_TOKEN: str`、`SEATS_DB_PATH: str`，全部从环境变量读取，缺失时有合理默认值。

- [ ] **Step 1: 写 `agent/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
pydantic==2.9.2
pytest==8.3.3
pytest-asyncio==0.24.0
# B: 请在此追加 openai SDK 等依赖，只追加不要删除已有行
```

- [ ] **Step 2: 写 `agent/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: 写 `agent/.env.example`**

```
# 数据服务层(Java)地址
SERVICE_BASE_URL=http://127.0.0.1:8080
# LLM 配置(B 使用)
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
# agent<->Java 内部鉴权 token(公网部署时才需要)
INTERNAL_TOKEN=
# 座位采集库路径(P2 座位预测读取)
SEATS_DB_PATH=collector/data/seats.db
```

- [ ] **Step 4: 写 `agent/config.py`**

```python
"""C 主维护的共享配置模块。所有配置从环境变量读取，缺失时给合理默认值，
不因缺少环境变量而在导入期报错。B/A 需要新配置项时请追加新的 os.getenv 行，
不要删除已有行。
"""
import os

SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "http://127.0.0.1:8080")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
SEATS_DB_PATH = os.getenv("SEATS_DB_PATH", "collector/data/seats.db")
```

- [ ] **Step 5: 写失败的测试 `agent/tests/test_config.py`**

```python
import importlib

import agent.config as config


def test_defaults_when_env_unset(monkeypatch):
    for key in [
        "SERVICE_BASE_URL", "LLM_BASE_URL", "LLM_API_KEY",
        "LLM_MODEL", "INTERNAL_TOKEN", "SEATS_DB_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)
    importlib.reload(config)
    assert config.SERVICE_BASE_URL == "http://127.0.0.1:8080"
    assert config.LLM_API_KEY == ""
    assert config.LLM_MODEL == "gpt-4o-mini"
    assert config.SEATS_DB_PATH == "collector/data/seats.db"


def test_env_override(monkeypatch):
    monkeypatch.setenv("SERVICE_BASE_URL", "http://example.com")
    importlib.reload(config)
    assert config.SERVICE_BASE_URL == "http://example.com"
    monkeypatch.delenv("SERVICE_BASE_URL", raising=False)
    importlib.reload(config)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_config.py -v`
Expected: PASS（因为 Step 4 已先写好实现，这一步是确认；若失败先检查 Step 4 内容与本步骤测试是否一致）

- [ ] **Step 7: Commit**

```bash
git add agent/requirements.txt agent/pytest.ini agent/.env.example agent/config.py agent/tests/test_config.py
git commit -m "feat(agent): 共享配置脚手架 requirements/config/env.example/pytest.ini"
```

---

## Task 2: 测试替身基础设施（FakeAgentLoop + httpx mock 工具）

**Files:**
- Create: `agent/tests/fakes.py`
- Test: `agent/tests/test_fakes.py`

**Interfaces:**
- Produces:
  - `FakeAgentResult`（dataclass，字段：`feature, output, memories_used, elapsed_ms, tokens, plan_note, used_llm, trace_id`，对齐契约②的 `AgentResult`）
  - `FakeAgentLoop`：`register_tool(name: str, fn: Callable) -> None`；`async def run(*, feature, subject, task, tool_name, tool_args, user_id, trace_id, query_key=None) -> FakeAgentResult`；`async def record_feedback(*, feedback, user_id, task_context="", trace_id="") -> list[str]`；属性 `run_calls: list[dict]`、`feedback_calls: list[dict]`、可设置的 `next_result: FakeAgentResult | None`、`next_feedback_ids: list[str]`
  - `envelope_response(status_code: int, code: int, msg: str, data=None) -> httpx.Response`：构造带信封 JSON body 的 httpx 响应，供后续任务的 `httpx.MockTransport` handler 使用

- [ ] **Step 1: 写失败的测试 `agent/tests/test_fakes.py`**

```python
import httpx
import pytest

from agent.tests.fakes import FakeAgentLoop, envelope_response


@pytest.mark.asyncio
async def test_fake_agent_loop_invokes_registered_tool():
    loop = FakeAgentLoop()

    async def tool(x: int, trace_id: str) -> int:
        return x * 2

    loop.register_tool("double", tool)

    result = await loop.run(
        feature="findbook", subject="s", task="t",
        tool_name="double", tool_args={"x": 21, "trace_id": "abc123"},
        user_id="u1", trace_id="abc123",
    )

    assert result.output == 42
    assert result.feature == "findbook"
    assert result.trace_id == "abc123"
    assert loop.run_calls[0]["tool_name"] == "double"
    assert loop.run_calls[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_fake_agent_loop_record_feedback_records_call_and_returns_ids():
    loop = FakeAgentLoop()
    loop.next_feedback_ids = ["mem-1"]

    ids = await loop.record_feedback(feedback="喜欢靠窗", user_id="u1", task_context="找书:x", trace_id="abc123")

    assert ids == ["mem-1"]
    assert loop.feedback_calls[0]["feedback"] == "喜欢靠窗"
    assert loop.feedback_calls[0]["task_context"] == "找书:x"


def test_envelope_response_builds_expected_json():
    resp = envelope_response(200, 0, "ok", {"a": 1})
    assert resp.status_code == 200
    assert resp.json() == {"code": 0, "msg": "ok", "data": {"a": 1}}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_fakes.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.tests.fakes'`）

- [ ] **Step 3: 写实现 `agent/tests/fakes.py`**

```python
"""C 名下的测试替身。用于在 B(AgentLoop)、A(Java) 交付前独立测试 C 的业务逻辑。
严格对齐 docs/接口契约.md 契约②的字段/签名。不导入 agent.core，避免 B 未交付时
测试因 ImportError 失败。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


@dataclass
class FakeAgentResult:
    feature: str
    output: Any
    memories_used: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    tokens: int = 0
    plan_note: str = ""
    used_llm: bool = False
    trace_id: str = ""


class FakeAgentLoop:
    """契约②(AgentLoop.run / record_feedback)的测试替身。"""

    def __init__(self) -> None:
        self.tools: dict[str, Callable] = {}
        self.run_calls: list[dict] = []
        self.feedback_calls: list[dict] = []
        self.next_result: FakeAgentResult | None = None
        self.next_feedback_ids: list[str] = ["fake-memory-id"]

    def register_tool(self, name: str, fn: Callable) -> None:
        self.tools[name] = fn

    async def run(
        self,
        *,
        feature: str,
        subject: str,
        task: str,
        tool_name: str,
        tool_args: dict,
        user_id: str,
        trace_id: str,
        query_key: str | None = None,
    ) -> FakeAgentResult:
        self.run_calls.append(
            dict(
                feature=feature, subject=subject, task=task,
                tool_name=tool_name, tool_args=tool_args,
                user_id=user_id, trace_id=trace_id, query_key=query_key,
            )
        )
        tool_fn = self.tools[tool_name]
        output = await tool_fn(**tool_args)
        if self.next_result is not None:
            result, self.next_result = self.next_result, None
            return result
        return FakeAgentResult(feature=feature, output=output, trace_id=trace_id)

    async def record_feedback(
        self,
        *,
        feedback: str,
        user_id: str,
        task_context: str = "",
        trace_id: str = "",
    ) -> list[str]:
        self.feedback_calls.append(
            dict(feedback=feedback, user_id=user_id, task_context=task_context, trace_id=trace_id)
        )
        return self.next_feedback_ids


def envelope_response(status_code: int, code: int, msg: str, data: Any = None) -> httpx.Response:
    """构造带 {code,msg,data} 信封的 httpx.Response，供 MockTransport handler 使用。"""
    return httpx.Response(status_code, json={"code": code, "msg": msg, "data": data})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_fakes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/tests/fakes.py agent/tests/test_fakes.py
git commit -m "test(agent): 加 FakeAgentLoop + envelope_response 测试替身"
```

---

## Task 3: `agent/service_client.py` —— 调 Java 层（契约①消费方）

**Files:**
- Create: `agent/service_client.py`
- Test: `agent/tests/test_service_client.py`

**Interfaces:**
- Consumes: `agent.tests.fakes.envelope_response`（Task 2）
- Produces:
  - `class ServiceError(Exception)`：属性 `code: int`, `msg: str`
  - `class ServiceUnavailable(Exception)`
  - `class ServiceClient.__init__(self, base_url: str, timeout: float = 5.0, internal_token: str | None = None, transport: httpx.BaseTransport | None = None)`
  - `async def search_books(self, query: str, page: int, page_size: int, trace_id: str) -> dict`
  - `async def seats_now(self, trace_id: str) -> dict`
  - `async def health(self, trace_id: str) -> dict`
  - `async def aclose(self) -> None`

- [ ] **Step 1: 写失败的测试 `agent/tests/test_service_client.py`**

```python
import httpx
import pytest

from agent.service_client import ServiceClient, ServiceError, ServiceUnavailable
from agent.tests.fakes import envelope_response


def _client(handler, monkeypatch, internal_token=None) -> ServiceClient:
    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("agent.service_client.asyncio.sleep", fast_sleep)
    transport = httpx.MockTransport(handler)
    return ServiceClient(base_url="http://java.internal", internal_token=internal_token, transport=transport)


@pytest.mark.asyncio
async def test_search_books_success_returns_data_and_sends_headers(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["params"] = dict(request.url.params)
        return envelope_response(200, 0, "ok", {"total": 1, "books": []})

    client = _client(handler, monkeypatch, internal_token="secret")
    data = await client.search_books("机器学习", 1, 10, trace_id="abc123")

    assert data == {"total": 1, "books": []}
    assert captured["headers"]["x-trace-id"] == "abc123"
    assert captured["headers"]["x-internal-token"] == "secret"
    assert captured["params"] == {"q": "机器学习", "page": "1", "pageSize": "10"}


@pytest.mark.asyncio
async def test_business_error_code_raises_service_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return envelope_response(200, 50001, "OPAC超时", None)

    client = _client(handler, monkeypatch)
    with pytest.raises(ServiceError) as exc_info:
        await client.search_books("q", 1, 10, trace_id="t1")
    assert exc_info.value.code == 50001
    assert exc_info.value.msg == "OPAC超时"


@pytest.mark.asyncio
async def test_timeout_retries_then_raises_service_unavailable(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.TimeoutException("boom")

    client = _client(handler, monkeypatch)
    with pytest.raises(ServiceUnavailable):
        await client.search_books("q", 1, 10, trace_id="t1")
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_429_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429)
        return envelope_response(200, 0, "ok", {"total": 0, "books": []})

    client = _client(handler, monkeypatch)
    data = await client.search_books("q", 1, 10, trace_id="t1")
    assert data == {"total": 0, "books": []}
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_4xx_does_not_retry(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404)

    client = _client(handler, monkeypatch)
    with pytest.raises(ServiceError):
        await client.search_books("q", 1, 10, trace_id="t1")
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_seats_now_and_health_call_expected_paths(monkeypatch):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return envelope_response(200, 0, "ok", {"status": "ok"})

    client = _client(handler, monkeypatch)
    await client.seats_now(trace_id="t1")
    await client.health(trace_id="t1")
    assert seen_paths == ["/api/seats/now", "/api/health"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_service_client.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.service_client'`）

- [ ] **Step 3: 写实现 `agent/service_client.py`**

```python
"""调 Java 数据服务层(契约①的消费方)。容错分层：超时/5xx/429 重试退避，
4xx(除429) 不重试直接报错。不做"Java挂了读采集库"的降级，那是
seat_predict/service.py 的职责。
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

_RETRYABLE_STATUS = {429}
_MAX_ATTEMPTS = 3
_BASE_DELAY = 0.5


class ServiceError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class ServiceUnavailable(Exception):
    pass


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        internal_token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        self._token = internal_token

    async def search_books(self, query: str, page: int, page_size: int, trace_id: str) -> dict:
        return await self._get(
            "/api/books/search",
            {"q": query, "page": page, "pageSize": page_size},
            trace_id,
        )

    async def seats_now(self, trace_id: str) -> dict:
        return await self._get("/api/seats/now", {}, trace_id)

    async def health(self, trace_id: str) -> dict:
        return await self._get("/api/health", {}, trace_id)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, trace_id: str) -> dict:
        headers = {"X-Trace-Id": trace_id}
        if self._token:
            headers["X-Internal-Token"] = self._token
        return headers

    async def _get(self, path: str, params: dict, trace_id: str) -> Any:
        headers = self._headers(trace_id)
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = await self._client.get(path, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt))
                    continue
                raise ServiceUnavailable(f"timeout calling {path}") from exc

            if response.status_code in _RETRYABLE_STATUS or response.status_code >= 500:
                last_error = ServiceUnavailable(f"HTTP {response.status_code} from {path}")
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_BASE_DELAY * (2**attempt))
                    continue
                raise last_error

            if response.status_code >= 400:
                raise ServiceError(response.status_code, f"HTTP {response.status_code} from {path}")

            body = response.json()
            code = body.get("code", 0)
            if code != 0:
                raise ServiceError(code, body.get("msg", ""))
            return body.get("data")

        raise ServiceUnavailable(f"exhausted retries for {path}") from last_error
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_service_client.py -v`
Expected: PASS（6 个测试全部通过）

- [ ] **Step 5: Commit**

```bash
git add agent/service_client.py agent/tests/test_service_client.py
git commit -m "feat(agent): 加 ServiceClient 调 Java 层, 分类重试+信封解析"
```

---

## Task 4: `agent/features/findbook/service.py` —— P0 找书

**Files:**
- Create: `agent/features/findbook/__init__.py`（空文件，仅为让路径可作为包导入，findbook 目录属 C 名下不算越界）
- Create: `agent/features/findbook/service.py`
- Test: `agent/tests/test_findbook_service.py`

**Interfaces:**
- Consumes:
  - `agent.service_client.ServiceClient`（Task 3）：`search_books`, `ServiceError`, `ServiceUnavailable`
  - `agent.tests.fakes.FakeAgentLoop`（Task 2，仅测试用）
  - 契约②签名：`agent_loop.run(feature, subject, task, tool_name, tool_args, user_id, trace_id, query_key=None)`；`agent_loop.record_feedback(feedback, user_id, task_context="", trace_id="")`
- Produces:
  - `class FindBookService.__init__(self, agent_loop, service_client: ServiceClient)`
  - `async def find(self, query: str, page: int, page_size: int, user_id: str, trace_id: str)`
  - `async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]`

- [ ] **Step 1: 建空 `agent/features/findbook/__init__.py`**

```python
```

- [ ] **Step 2: 写失败的测试 `agent/tests/test_findbook_service.py`**

```python
import pytest

from agent.features.findbook.service import FindBookService
from agent.service_client import ServiceUnavailable
from agent.tests.fakes import FakeAgentLoop


class _StubServiceClient:
    def __init__(self):
        self.calls = []
        self.raise_error: Exception | None = None
        self.result = {"total": 1, "page": 1, "pageSize": 10, "books": [{"title": "机器学习"}]}

    async def search_books(self, query, page, page_size, trace_id):
        self.calls.append(dict(query=query, page=page, page_size=page_size, trace_id=trace_id))
        if self.raise_error is not None:
            raise self.raise_error
        return self.result


@pytest.mark.asyncio
async def test_find_runs_agent_loop_with_query_key_and_returns_result():
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    service = FindBookService(loop, stub)

    result = await service.find("机器学习", 1, 10, user_id="u1", trace_id="abc123")

    assert result.output == stub.result
    call = loop.run_calls[0]
    assert call["feature"] == "findbook"
    assert call["tool_name"] == "search_books"
    assert call["query_key"] == "query"
    assert call["tool_args"]["query"] == "机器学习"
    assert call["user_id"] == "u1"
    assert call["trace_id"] == "abc123"
    assert stub.calls[0]["query"] == "机器学习"


@pytest.mark.asyncio
async def test_find_tool_degrades_on_service_unavailable():
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    stub.raise_error = ServiceUnavailable("boom")
    service = FindBookService(loop, stub)

    result = await service.find("机器学习", 1, 10, user_id="u1", trace_id="abc123")

    assert result.output == {"error": "图书检索服务暂时不可用，请稍后再试"}


@pytest.mark.asyncio
async def test_feedback_delegates_to_agent_loop_record_feedback():
    loop = FakeAgentLoop()
    loop.next_feedback_ids = ["mem-1"]
    stub = _StubServiceClient()
    service = FindBookService(loop, stub)

    ids = await service.feedback("这本书不错", user_id="u1", trace_id="abc123")

    assert ids == ["mem-1"]
    call = loop.feedback_calls[0]
    assert call["feedback"] == "这本书不错"
    assert call["user_id"] == "u1"
    assert call["task_context"] == "找书:这本书不错"
    assert call["trace_id"] == "abc123"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_findbook_service.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.features.findbook.service'`）

- [ ] **Step 4: 写实现 `agent/features/findbook/service.py`**

```python
"""P0 找书功能。注册 search_books 工具给 AgentLoop(契约②)，通过依赖注入
持有 agent_loop 与 service_client，不在模块顶层导入全局单例。
"""
from __future__ import annotations

from agent.service_client import ServiceError, ServiceUnavailable


class FindBookService:
    def __init__(self, agent_loop, service_client):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._agent_loop.register_tool("search_books", self._search_books_tool)

    async def _search_books_tool(self, query: str, page: int, page_size: int, trace_id: str) -> dict:
        try:
            return await self._service_client.search_books(query, page, page_size, trace_id)
        except (ServiceError, ServiceUnavailable):
            return {"error": "图书检索服务暂时不可用，请稍后再试"}

    async def find(self, query: str, page: int, page_size: int, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="findbook",
            subject="找书",
            task=f"查询: {query}",
            tool_name="search_books",
            tool_args={"query": query, "page": page, "page_size": page_size, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key="query",
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"找书:{feedback[:30]}",
            trace_id=trace_id,
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_findbook_service.py -v`
Expected: PASS（3 个测试全部通过）

- [ ] **Step 6: Commit**

```bash
git add agent/features/findbook/__init__.py agent/features/findbook/service.py agent/tests/test_findbook_service.py
git commit -m "feat(agent): 加 FindBookService, 注入 agent_loop+service_client"
```

---

## Task 5: `agent/features/knowledge_map/semantic_scholar.py` + `s2_cache.py`

**Files:**
- Create: `agent/features/knowledge_map/__init__.py`
- Create: `agent/features/knowledge_map/semantic_scholar.py`
- Create: `agent/features/knowledge_map/s2_cache.py`
- Test: `agent/tests/test_semantic_scholar.py`
- Test: `agent/tests/test_s2_cache.py`

**Interfaces:**
- Produces:
  - `class SemanticScholarClient.__init__(self, base_url="https://api.semanticscholar.org/graph/v1", timeout=10.0, transport=None)`
  - `async def search(self, query: str, limit: int = 10) -> list[dict]`
  - `async def paper(self, paper_id: str) -> dict`
  - `async def references(self, paper_id: str, limit: int = 20) -> list[dict]`（展平 `data[].citedPaper`）
  - `class S2Cache.__init__(self, path: str)`；`get(self, key: str) -> dict | None`；`set(self, key: str, value: dict) -> None`

- [ ] **Step 1: 建空 `agent/features/knowledge_map/__init__.py`**

```python
```

- [ ] **Step 2: 写失败的测试 `agent/tests/test_semantic_scholar.py`**

```python
import httpx
import pytest

from agent.features.knowledge_map.semantic_scholar import SemanticScholarClient


def _client(handler, monkeypatch) -> SemanticScholarClient:
    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("agent.features.knowledge_map.semantic_scholar.asyncio.sleep", fast_sleep)
    transport = httpx.MockTransport(handler)
    return SemanticScholarClient(transport=transport)


@pytest.mark.asyncio
async def test_search_returns_data_list(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/search"
        return httpx.Response(200, json={"data": [{"paperId": "p1", "title": "A"}]})

    client = _client(handler, monkeypatch)
    results = await client.search("attention is all you need", limit=5)
    assert results == [{"paperId": "p1", "title": "A"}]


@pytest.mark.asyncio
async def test_paper_returns_single_dict(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/p1"
        return httpx.Response(200, json={"paperId": "p1", "title": "A"})

    client = _client(handler, monkeypatch)
    result = await client.paper("p1")
    assert result == {"paperId": "p1", "title": "A"}


@pytest.mark.asyncio
async def test_references_flattens_cited_paper(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/paper/p1/references"
        return httpx.Response(
            200,
            json={"data": [{"citedPaper": {"paperId": "p2", "title": "B"}}, {"citedPaper": {"paperId": "p3", "title": "C"}}]},
        )

    client = _client(handler, monkeypatch)
    results = await client.references("p1", limit=20)
    assert results == [{"paperId": "p2", "title": "B"}, {"paperId": "p3", "title": "C"}]


@pytest.mark.asyncio
async def test_429_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"data": []})

    client = _client(handler, monkeypatch)
    results = await client.search("q")
    assert results == []
    assert calls["count"] == 3
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_semantic_scholar.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 4: 写实现 `agent/features/knowledge_map/semantic_scholar.py`**

```python
"""Semantic Scholar Graph API 客户端(P1 知识地图数据源, 免费无需VPN)。
429 限流严重，指数退避重试。"""
from __future__ import annotations

import asyncio

import httpx

_MAX_ATTEMPTS = 3
_BASE_DELAY = 1.0


class SemanticScholarClient:
    def __init__(
        self,
        base_url: str = "https://api.semanticscholar.org/graph/v1",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        body = await self._get(
            "/paper/search",
            {"query": query, "limit": limit, "fields": "paperId,title,year,abstract,authors"},
        )
        return body.get("data", [])

    async def paper(self, paper_id: str) -> dict:
        return await self._get(f"/paper/{paper_id}", {"fields": "paperId,title,year,abstract,authors"})

    async def references(self, paper_id: str, limit: int = 20) -> list[dict]:
        body = await self._get(
            f"/paper/{paper_id}/references",
            {"limit": limit, "fields": "paperId,title,year"},
        )
        return [item["citedPaper"] for item in body.get("data", [])]

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict) -> dict:
        for attempt in range(_MAX_ATTEMPTS):
            response = await self._client.get(path, params=params)
            if response.status_code == 429 and attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_BASE_DELAY * (2**attempt))
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_semantic_scholar.py -v`
Expected: PASS（4 个测试全部通过）

- [ ] **Step 6: 写失败的测试 `agent/tests/test_s2_cache.py`**

```python
import json

from agent.features.knowledge_map.s2_cache import S2Cache


def test_get_returns_none_when_missing(tmp_path):
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    assert cache.get("paper:p1") is None


def test_set_then_get_roundtrips(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = S2Cache(path=str(cache_path))
    cache.set("paper:p1", {"title": "A"})
    assert cache.get("paper:p1") == {"title": "A"}

    reloaded = S2Cache(path=str(cache_path))
    assert reloaded.get("paper:p1") == {"title": "A"}


def test_set_persists_valid_json_file(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = S2Cache(path=str(cache_path))
    cache.set("k", {"v": 1})
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"k": {"v": 1}}
```

- [ ] **Step 7: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_s2_cache.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 8: 写实现 `agent/features/knowledge_map/s2_cache.py`**

```python
"""S2 持久缓存(横切关注点②C的一半)。引用关系稳定，缓存显著降低429。
JSON 文件缓存，纯 key-value，不知道 HTTP 细节。"""
from __future__ import annotations

import json
import os


class S2Cache:
    def __init__(self, path: str = "agent/features/knowledge_map/.s2_cache.json"):
        self._path = path

    def get(self, key: str) -> dict | None:
        data = self._load()
        return data.get(key)

    def set(self, key: str, value: dict) -> None:
        data = self._load()
        data[key] = value
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)
```

- [ ] **Step 9: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_s2_cache.py -v`
Expected: PASS（3 个测试全部通过）

- [ ] **Step 10: Commit**

```bash
git add agent/features/knowledge_map/__init__.py agent/features/knowledge_map/semantic_scholar.py agent/features/knowledge_map/s2_cache.py agent/tests/test_semantic_scholar.py agent/tests/test_s2_cache.py
git commit -m "feat(agent): 加 SemanticScholarClient(429退避) + S2Cache(JSON持久缓存)"
```

---

## Task 6: `agent/features/knowledge_map/service.py` —— P1 知识地图

**Files:**
- Create: `agent/features/knowledge_map/service.py`
- Test: `agent/tests/test_knowledge_map_service.py`

**Interfaces:**
- Consumes:
  - `agent.features.knowledge_map.semantic_scholar.SemanticScholarClient`（Task 5）：`references(paper_id, limit)`, `paper(paper_id)`
  - `agent.features.knowledge_map.s2_cache.S2Cache`（Task 5）：`get(key)`, `set(key, value)`
  - `agent.tests.fakes.FakeAgentLoop`（Task 2，仅测试用）
- Produces:
  - `class KnowledgeMapService.__init__(self, agent_loop, s2_client, s2_cache)`
  - `async def build_graph(self, paper_id: str, user_id: str, trace_id: str)`
  - `async def summarize(self, paper_id: str, user_id: str, trace_id: str)`

- [ ] **Step 1: 写失败的测试 `agent/tests/test_knowledge_map_service.py`**

```python
import pytest

from agent.features.knowledge_map.s2_cache import S2Cache
from agent.features.knowledge_map.service import KnowledgeMapService
from agent.tests.fakes import FakeAgentLoop


class _StubS2Client:
    def __init__(self):
        self.reference_calls = []
        self.paper_calls = []
        self.references_result = [{"paperId": "p2", "title": "B"}]
        self.paper_result = {"paperId": "p1", "title": "A", "abstract": "abs"}

    async def references(self, paper_id, limit=20):
        self.reference_calls.append(paper_id)
        return self.references_result

    async def paper(self, paper_id):
        self.paper_calls.append(paper_id)
        return self.paper_result


@pytest.mark.asyncio
async def test_build_graph_calls_agent_loop_with_build_citation_graph_tool(tmp_path):
    loop = FakeAgentLoop()
    s2 = _StubS2Client()
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    service = KnowledgeMapService(loop, s2, cache)

    result = await service.build_graph("p1", user_id="u1", trace_id="abc123")

    call = loop.run_calls[0]
    assert call["feature"] == "knowledge_map"
    assert call["tool_name"] == "build_citation_graph"
    assert call["query_key"] is None
    assert call["tool_args"]["paper_id"] == "p1"
    assert result.output["nodes"][0]["paperId"] == "p1"
    assert {"paperId": "p2", "title": "B"} in [
        {"paperId": n["paperId"], "title": n["title"]} for n in result.output["nodes"][1:]
    ]
    assert s2.reference_calls == ["p1"]


@pytest.mark.asyncio
async def test_build_graph_uses_cache_on_second_call(tmp_path):
    loop = FakeAgentLoop()
    s2 = _StubS2Client()
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    service = KnowledgeMapService(loop, s2, cache)

    await service.build_graph("p1", user_id="u1", trace_id="t1")
    await service.build_graph("p1", user_id="u1", trace_id="t2")

    assert s2.reference_calls == ["p1"]  # 第二次命中缓存，不再打 S2


@pytest.mark.asyncio
async def test_summarize_calls_agent_loop_with_summarize_tool(tmp_path):
    loop = FakeAgentLoop()
    s2 = _StubS2Client()
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    service = KnowledgeMapService(loop, s2, cache)

    result = await service.summarize("p1", user_id="u1", trace_id="abc123")

    call = loop.run_calls[0]
    assert call["feature"] == "knowledge_map"
    assert call["tool_name"] == "summarize_paper"
    assert call["query_key"] is None
    assert result.output["paperId"] == "p1"
    assert s2.paper_calls == ["p1"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_knowledge_map_service.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.features.knowledge_map.service'`）

- [ ] **Step 3: 写实现 `agent/features/knowledge_map/service.py`**

```python
"""P1 知识地图功能。build_citation_graph 工具不需要 LLM，直接组装引用图；
summarize_paper 工具只取回原始论文数据交给 planner/LLM 生成摘要
(是否调用 LLM 是 agent_loop 内部的事，本类不关心)。
"""
from __future__ import annotations


class KnowledgeMapService:
    def __init__(self, agent_loop, s2_client, s2_cache):
        self._agent_loop = agent_loop
        self._s2 = s2_client
        self._cache = s2_cache
        self._agent_loop.register_tool("build_citation_graph", self._build_graph_tool)
        self._agent_loop.register_tool("summarize_paper", self._summarize_tool)

    async def _build_graph_tool(self, paper_id: str, trace_id: str) -> dict:
        cache_key = f"references:{paper_id}"
        cited = self._cache.get(cache_key)
        if cited is None:
            cited = await self._s2.references(paper_id)
            self._cache.set(cache_key, cited)
        nodes = [{"paperId": paper_id}] + cited
        edges = [{"source": paper_id, "target": item["paperId"]} for item in cited]
        return {"nodes": nodes, "edges": edges}

    async def _summarize_tool(self, paper_id: str, trace_id: str) -> dict:
        cache_key = f"paper:{paper_id}"
        detail = self._cache.get(cache_key)
        if detail is None:
            detail = await self._s2.paper(paper_id)
            self._cache.set(cache_key, detail)
        return detail

    async def build_graph(self, paper_id: str, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="knowledge_map",
            subject="知识地图",
            task=f"构建引用图: {paper_id}",
            tool_name="build_citation_graph",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )

    async def summarize(self, paper_id: str, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="knowledge_map",
            subject="知识地图",
            task=f"摘要: {paper_id}",
            tool_name="summarize_paper",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_knowledge_map_service.py -v`
Expected: PASS（3 个测试全部通过）

- [ ] **Step 5: Commit**

```bash
git add agent/features/knowledge_map/service.py agent/tests/test_knowledge_map_service.py
git commit -m "feat(agent): 加 KnowledgeMapService, build_citation_graph+summarize_paper 工具"
```

---

## Task 7: `agent/features/seat_predict/service.py` —— P2 座位预测（笨基线）

**Files:**
- Create: `agent/features/seat_predict/__init__.py`
- Create: `agent/features/seat_predict/service.py`
- Test: `agent/tests/test_seat_predict.py`

**Interfaces:**
- Consumes:
  - `agent.service_client.ServiceClient`（Task 3）：`seats_now(trace_id)`, `ServiceUnavailable`
  - `agent.tests.fakes.FakeAgentLoop`（Task 2，仅测试用）
- Produces:
  - `class SeatPredictService.__init__(self, agent_loop, service_client, seats_db_path: str)`
  - `async def predict(self, weekday: int, hour: int, user_id: str, trace_id: str)`
  - `async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]`

⚠️ 假定 `seats_db_path` 指向的 SQLite 库中存在表 `seat_snapshots(weekday INTEGER, hour INTEGER, area_name TEXT, occupied INTEGER, total INTEGER)`。此 schema 未在接口契约中定义，需与 A 确认；若实际字段不同，只需修改本任务 Step 4 中 `_predict_tool` 里的一处 SQL。

- [ ] **Step 1: 建空 `agent/features/seat_predict/__init__.py`**

```python
```

- [ ] **Step 2: 写失败的测试 `agent/tests/test_seat_predict.py`**

```python
import sqlite3

import pytest

from agent.features.seat_predict.service import SeatPredictService
from agent.service_client import ServiceUnavailable
from agent.tests.fakes import FakeAgentLoop


def _make_seats_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE seat_snapshots (weekday INTEGER, hour INTEGER, area_name TEXT, occupied INTEGER, total INTEGER)"
    )
    rows = [
        (1, 14, "301阅览室", 140, 175),
        (1, 14, "301阅览室", 120, 175),
        (1, 14, "201文艺期刊阅览室", 30, 175),
        (1, 14, "201文艺期刊阅览室", 50, 175),
    ]
    conn.executemany(
        "INSERT INTO seat_snapshots (weekday, hour, area_name, occupied, total) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


class _StubServiceClient:
    def __init__(self):
        self.raise_error: Exception | None = None

    async def seats_now(self, trace_id):
        if self.raise_error is not None:
            raise self.raise_error
        return {"count": 1, "areas": []}


@pytest.mark.asyncio
async def test_predict_sorts_areas_by_ascending_occupancy_rate(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    ranking = result.output["ranking"]
    assert ranking[0]["area_name"] == "201文艺期刊阅览室"
    assert ranking[0]["avg_occupancy_rate"] == pytest.approx(40 / 175)
    assert ranking[1]["area_name"] == "301阅览室"
    assert ranking[1]["avg_occupancy_rate"] == pytest.approx(130 / 175)


@pytest.mark.asyncio
async def test_predict_ignores_realtime_correction_when_service_unavailable(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    stub.raise_error = ServiceUnavailable("boom")
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    assert len(result.output["ranking"]) == 2
    assert result.output.get("realtime_available") is False


@pytest.mark.asyncio
async def test_feedback_delegates_to_agent_loop_record_feedback(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    loop.next_feedback_ids = ["mem-2"]
    stub = _StubServiceClient()
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

    ids = await service.feedback("这层其实很吵", user_id="u1", trace_id="abc123")

    assert ids == ["mem-2"]
    call = loop.feedback_calls[0]
    assert call["task_context"] == "座位纠错:这层其实很吵"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_seat_predict.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.features.seat_predict.service'`）

- [ ] **Step 4: 写实现 `agent/features/seat_predict/service.py`**

```python
"""P2 座位预测(笨基线)。同 weekday+同时段历史平均占用率升序排序推荐，
稳、可解释，先上线顶着，日后可当模型对照组。只读连接设 busy_timeout，
不建表不设WAL(建库/WAL 是采集器/A 的职责)。

⚠️ 假定表结构 seat_snapshots(weekday, hour, area_name, occupied, total)，
未在接口契约中定义，需与 A 确认；若实际字段不同，只需改本文件 SQL。
"""
from __future__ import annotations

import sqlite3

from agent.service_client import ServiceUnavailable


class SeatPredictService:
    def __init__(self, agent_loop, service_client, seats_db_path: str):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._db_path = seats_db_path
        self._agent_loop.register_tool("predict_seats", self._predict_tool)

    def _read_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _predict_tool(self, weekday: int, hour: int, trace_id: str) -> dict:
        conn = self._read_conn()
        try:
            rows = conn.execute(
                """
                SELECT area_name, AVG(occupied) AS avg_occupied, AVG(total) AS avg_total
                FROM seat_snapshots
                WHERE weekday = ? AND hour = ?
                GROUP BY area_name
                """,
                (weekday, hour),
            ).fetchall()
        finally:
            conn.close()

        ranking = [
            {
                "area_name": area_name,
                "avg_occupancy_rate": (avg_occupied / avg_total) if avg_total else 0.0,
            }
            for area_name, avg_occupied, avg_total in rows
        ]
        ranking.sort(key=lambda item: item["avg_occupancy_rate"])

        realtime_available = True
        try:
            await self._service_client.seats_now(trace_id)
        except ServiceUnavailable:
            realtime_available = False

        return {"ranking": ranking, "realtime_available": realtime_available}

    async def predict(self, weekday: int, hour: int, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="seat_predict",
            subject="座位预测",
            task=f"预测: weekday={weekday} hour={hour}",
            tool_name="predict_seats",
            tool_args={"weekday": weekday, "hour": hour, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"座位纠错:{feedback[:30]}",
            trace_id=trace_id,
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_seat_predict.py -v`
Expected: PASS（3 个测试全部通过）

- [ ] **Step 6: Commit**

```bash
git add agent/features/seat_predict/__init__.py agent/features/seat_predict/service.py agent/tests/test_seat_predict.py
git commit -m "feat(agent): 加 SeatPredictService 笨基线(历史占用率排序+busy_timeout)"
```

---

## Task 8: `agent/benchmark/harness.py` —— 04 赛道指标面板

**Files:**
- Create: `agent/benchmark/__init__.py`
- Create: `agent/benchmark/harness.py`
- Test: `agent/tests/test_benchmark_harness.py`

**Interfaces:**
- Consumes: `agent.features.findbook.service.FindBookService`（Task 4）：`find(query, page, page_size, user_id, trace_id)`
- Produces:
  - `@dataclass TaskMetric`：字段 `task_name: str, elapsed_ms: float, tokens: int, memory_hit: bool, used_llm: bool`
  - `class BenchmarkHarness.__init__(self, findbook_service)`
  - `async def run_task(self, query: str, user_id: str, trace_id: str) -> TaskMetric`
  - `async def run_batch(self, queries: list[str], user_id: str = "benchmark") -> list[TaskMetric]`
  - `def report(self) -> dict`（含 `avg_elapsed_ms`, `total_tokens`, `memory_hit_rate`, `memory_misuse_rate`）
  - `def to_markdown(self) -> str`

- [ ] **Step 1: 建空 `agent/benchmark/__init__.py`**

```python
```

- [ ] **Step 2: 写失败的测试 `agent/tests/test_benchmark_harness.py`**

```python
import pytest

from agent.benchmark.harness import BenchmarkHarness, TaskMetric
from agent.features.findbook.service import FindBookService
from agent.tests.fakes import FakeAgentLoop, FakeAgentResult


class _StubServiceClient:
    async def search_books(self, query, page, page_size, trace_id):
        return {"total": 1, "books": [{"title": query}]}


@pytest.mark.asyncio
async def test_run_task_returns_metric_from_agent_result():
    loop = FakeAgentLoop()
    loop.next_result = FakeAgentResult(
        feature="findbook", output={"books": []}, memories_used=["m1"],
        elapsed_ms=12.5, tokens=42, used_llm=True, trace_id="abc123",
    )
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)

    metric = await harness.run_task("机器学习", user_id="benchmark", trace_id="abc123")

    assert metric == TaskMetric(
        task_name="机器学习", elapsed_ms=12.5, tokens=42, memory_hit=True, used_llm=True,
    )


@pytest.mark.asyncio
async def test_run_batch_collects_one_metric_per_query():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)

    metrics = await harness.run_batch(["机器学习", "数据结构"])

    assert [m.task_name for m in metrics] == ["机器学习", "数据结构"]
    assert len(harness._metrics) == 2


@pytest.mark.asyncio
async def test_report_aggregates_metrics():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)
    harness._metrics = [
        TaskMetric(task_name="a", elapsed_ms=10.0, tokens=5, memory_hit=True, used_llm=True),
        TaskMetric(task_name="b", elapsed_ms=20.0, tokens=15, memory_hit=False, used_llm=True),
    ]

    report = harness.report()

    assert report["avg_elapsed_ms"] == pytest.approx(15.0)
    assert report["total_tokens"] == 20
    assert report["memory_hit_rate"] == pytest.approx(0.5)
    assert report["memory_misuse_rate"] == "待人工标注"


def test_to_markdown_includes_report_fields():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)
    harness._metrics = [
        TaskMetric(task_name="a", elapsed_ms=10.0, tokens=5, memory_hit=True, used_llm=True),
    ]

    markdown = harness.to_markdown()

    assert "avg_elapsed_ms" in markdown
    assert "memory_hit_rate" in markdown
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_benchmark_harness.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.benchmark.harness'`）

- [ ] **Step 4: 写实现 `agent/benchmark/harness.py`**

```python
"""04 赛道 FOCUS 指标采集。跑一批找书任务, 聚合 token成本/延迟/记忆命中率。
记忆误用率需人工标注负反馈样本，本轮不做自动化，报告里留字符串占位说明。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass


@dataclass(eq=True)
class TaskMetric:
    task_name: str
    elapsed_ms: float
    tokens: int
    memory_hit: bool
    used_llm: bool


class BenchmarkHarness:
    def __init__(self, findbook_service):
        self._findbook = findbook_service
        self._metrics: list[TaskMetric] = []

    async def run_task(self, query: str, user_id: str, trace_id: str) -> TaskMetric:
        result = await self._findbook.find(query, page=1, page_size=10, user_id=user_id, trace_id=trace_id)
        metric = TaskMetric(
            task_name=query,
            elapsed_ms=result.elapsed_ms,
            tokens=result.tokens,
            memory_hit=len(result.memories_used) > 0,
            used_llm=result.used_llm,
        )
        self._metrics.append(metric)
        return metric

    async def run_batch(self, queries: list[str], user_id: str = "benchmark") -> list[TaskMetric]:
        results = []
        for query in queries:
            trace_id = uuid.uuid4().hex[:8]
            results.append(await self.run_task(query, user_id=user_id, trace_id=trace_id))
        return results

    def report(self) -> dict:
        if not self._metrics:
            return {
                "avg_elapsed_ms": 0.0, "total_tokens": 0,
                "memory_hit_rate": 0.0, "memory_misuse_rate": "待人工标注",
            }
        total = len(self._metrics)
        return {
            "avg_elapsed_ms": sum(m.elapsed_ms for m in self._metrics) / total,
            "total_tokens": sum(m.tokens for m in self._metrics),
            "memory_hit_rate": sum(1 for m in self._metrics if m.memory_hit) / total,
            "memory_misuse_rate": "待人工标注",
        }

    def to_markdown(self) -> str:
        report = self.report()
        lines = ["# Benchmark Report", ""]
        for key, value in report.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_benchmark_harness.py -v`
Expected: PASS（4 个测试全部通过）

- [ ] **Step 6: Commit**

```bash
git add agent/benchmark/__init__.py agent/benchmark/harness.py agent/tests/test_benchmark_harness.py
git commit -m "feat(agent): 加 BenchmarkHarness, 04赛道token/延迟/记忆命中率聚合"
```

---

## Task 9: `agent/main.py` —— FastAPI 入口 + 路由（信封/异常处理可独立测试，装配部分预期依赖 B）

**Files:**
- Create: `agent/__init__.py`
- Create: `agent/envelope.py`
- Create: `agent/main.py`
- Test: `agent/tests/test_envelope.py`
- Test: `agent/tests/test_main_routes.py`

**Interfaces:**
- Consumes:
  - `agent.features.findbook.service.FindBookService`（Task 4）
  - `agent.features.knowledge_map.service.KnowledgeMapService`（Task 6）
  - `agent.features.seat_predict.service.SeatPredictService`（Task 7）
  - `agent.service_client.ServiceClient`（Task 3）
  - `agent.config`（Task 1）：`SERVICE_BASE_URL`, `INTERNAL_TOKEN`, `SEATS_DB_PATH`
  - 契约②：`from agent.core.agent_loop import AgentLoop`（B 未交付前触发 `ImportError`，这是预期状态，本任务的路由测试通过依赖覆盖规避真实装配，不依赖该 import 成功）
- Produces:
  - `agent/envelope.py`: `def envelope(code: int, msg: str, data=None) -> dict`；`class AgentError(Exception)`（属性 `code: int, msg: str`，供路由层统一转换成信封错误响应)
  - `agent/main.py`: FastAPI `app` 对象；路由 `POST /findbook/search`、`POST /findbook/feedback`、`POST /knowledge/graph`、`POST /knowledge/summarize`、`POST /seat/predict`、`POST /seat/feedback`、`POST /memory/feedback`、`GET /health`；FastAPI dependency-override 挂点：`app.dependency_overrides[get_findbook_service]` 等（供测试注入假 service，不依赖真实 AgentLoop）

- [ ] **Step 1: 建空 `agent/__init__.py`**

```python
```

- [ ] **Step 2: 写失败的测试 `agent/tests/test_envelope.py`**

```python
from agent.envelope import AgentError, envelope


def test_envelope_success_shape():
    result = envelope(0, "ok", {"a": 1})
    assert result == {"code": 0, "msg": "ok", "data": {"a": 1}}


def test_envelope_error_shape_has_null_data():
    result = envelope(60001, "LLM 不可用")
    assert result == {"code": 60001, "msg": "LLM 不可用", "data": None}


def test_agent_error_carries_code_and_msg():
    err = AgentError(60002, "记忆库异常")
    assert err.code == 60002
    assert err.msg == "记忆库异常"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_envelope.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.envelope'`）

- [ ] **Step 4: 写实现 `agent/envelope.py`**

```python
"""统一响应信封 {code, msg, data}（docs/接口契约.md 全局约定）。"""
from __future__ import annotations

from typing import Any


class AgentError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


def envelope(code: int, msg: str, data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_envelope.py -v`
Expected: PASS（3 个测试全部通过）

- [ ] **Step 6: 写失败的测试 `agent/tests/test_main_routes.py`**

本测试通过 FastAPI 的 `app.dependency_overrides` 注入假 service，不触发对 `agent.core.agent_loop` 的真实 import，因此在 B 未交付时也能独立运行。

```python
import pytest
from fastapi.testclient import TestClient

from agent.main import app, get_findbook_service
from agent.tests.fakes import FakeAgentLoop, FakeAgentResult


class _StubServiceClient:
    async def search_books(self, query, page, page_size, trace_id):
        return {"total": 1, "books": [{"title": query}]}


@pytest.fixture
def client():
    from agent.features.findbook.service import FindBookService

    loop = FakeAgentLoop()
    loop.next_result = FakeAgentResult(
        feature="findbook", output={"total": 1, "books": [{"title": "机器学习"}]},
        memories_used=[], elapsed_ms=5.0, tokens=0, used_llm=False, trace_id="abc123",
    )
    service = FindBookService(loop, _StubServiceClient())
    app.dependency_overrides[get_findbook_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_findbook_search_returns_enveloped_response(client):
    response = client.post(
        "/findbook/search",
        json={"query": "机器学习", "page": 1, "page_size": 10},
        headers={"X-User-Id": "u1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["books"][0]["title"] == "机器学习"


def test_findbook_search_defaults_user_id_when_header_missing(client):
    response = client.post("/findbook/search", json={"query": "q", "page": 1, "page_size": 10})
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_health_route_returns_envelope_shape(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert "status" in body["data"] or "agent" in body["data"]
```

- [ ] **Step 7: 运行测试确认失败**

Run: `python -m pytest agent/tests/test_main_routes.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'agent.main'`）

- [ ] **Step 8: 写实现 `agent/main.py`**

```python
"""FastAPI 入口。装配三功能单例 + 定义路由。

⚠️ 下方 `from agent.core.agent_loop import AgentLoop` 在 B 交付前会
ImportError——这是预期状态：main.py 能否启动如实反映 A/B 的交付进度，
不伪造可运行假象。路由层通过 FastAPI dependency-override 支持独立测试，
不依赖这一行的 import 成功。
"""
from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from agent import config
from agent.envelope import AgentError, envelope
from agent.features.findbook.service import FindBookService
from agent.features.knowledge_map.s2_cache import S2Cache
from agent.features.knowledge_map.semantic_scholar import SemanticScholarClient
from agent.features.knowledge_map.service import KnowledgeMapService
from agent.features.seat_predict.service import SeatPredictService
from agent.service_client import ServiceClient, ServiceError, ServiceUnavailable

app = FastAPI(title="library-patch agent")

_service_client = ServiceClient(base_url=config.SERVICE_BASE_URL, internal_token=config.INTERNAL_TOKEN or None)
_findbook_service: FindBookService | None = None
_knowledge_service: KnowledgeMapService | None = None
_seat_service: SeatPredictService | None = None
_agent_loop = None


@app.on_event("startup")
def _assemble_services() -> None:
    global _findbook_service, _knowledge_service, _seat_service, _agent_loop
    from agent.core.agent_loop import AgentLoop  # noqa: PLC0415 — 见模块docstring, B交付前预期ImportError

    _agent_loop = AgentLoop()
    _findbook_service = FindBookService(_agent_loop, _service_client)
    _knowledge_service = KnowledgeMapService(_agent_loop, SemanticScholarClient(), S2Cache())
    _seat_service = SeatPredictService(_agent_loop, _service_client, seats_db_path=config.SEATS_DB_PATH)


def get_findbook_service() -> FindBookService:
    if _findbook_service is None:
        raise AgentError(60001, "服务未初始化(B层依赖未就绪)")
    return _findbook_service


def get_knowledge_service() -> KnowledgeMapService:
    if _knowledge_service is None:
        raise AgentError(60001, "服务未初始化(B层依赖未就绪)")
    return _knowledge_service


def get_seat_service() -> SeatPredictService:
    if _seat_service is None:
        raise AgentError(60001, "服务未初始化(B层依赖未就绪)")
    return _seat_service


def _user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    return x_user_id or "default"


def _trace_id(x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")) -> str:
    return x_trace_id or uuid.uuid4().hex[:8]


@app.exception_handler(AgentError)
async def _agent_error_handler(request: Request, exc: AgentError):
    return JSONResponse(status_code=200, content=envelope(exc.code, exc.msg))


@app.exception_handler(ServiceError)
async def _service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=200, content=envelope(exc.code, exc.msg))


@app.exception_handler(ServiceUnavailable)
async def _service_unavailable_handler(request: Request, exc: ServiceUnavailable):
    return JSONResponse(status_code=200, content=envelope(50001, "数据服务暂时不可用"))


@app.post("/findbook/search")
async def findbook_search(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: FindBookService = Depends(get_findbook_service),
):
    result = await service.find(
        query=body["query"], page=body.get("page", 1), page_size=body.get("page_size", 10),
        user_id=user_id, trace_id=trace_id,
    )
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/findbook/feedback")
async def findbook_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: FindBookService = Depends(get_findbook_service),
):
    ids = await service.feedback(feedback=body["feedback"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", {"memory_ids": ids})


@app.post("/knowledge/graph")
async def knowledge_graph(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: KnowledgeMapService = Depends(get_knowledge_service),
):
    result = await service.build_graph(paper_id=body["paper_id"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/knowledge/summarize")
async def knowledge_summarize(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: KnowledgeMapService = Depends(get_knowledge_service),
):
    result = await service.summarize(paper_id=body["paper_id"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/seat/predict")
async def seat_predict(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: SeatPredictService = Depends(get_seat_service),
):
    result = await service.predict(
        weekday=body["weekday"], hour=body["hour"], user_id=user_id, trace_id=trace_id,
    )
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/seat/feedback")
async def seat_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: SeatPredictService = Depends(get_seat_service),
):
    ids = await service.feedback(feedback=body["feedback"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", {"memory_ids": ids})


@app.post("/memory/feedback")
async def memory_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
):
    if _agent_loop is None:
        raise AgentError(60001, "记忆服务未初始化(B层依赖未就绪)")
    ids = await _agent_loop.record_feedback(
        feedback=body["feedback"], user_id=user_id,
        task_context=body.get("task_context", ""), trace_id=trace_id,
    )
    return envelope(0, "ok", {"memory_ids": ids})


@app.get("/health")
async def health(trace_id: str = Depends(_trace_id)):
    agent_status = "ok"
    java_status: dict = {}
    try:
        java_status = await _service_client.health(trace_id)
    except (ServiceError, ServiceUnavailable):
        java_status = {"status": "unavailable"}
    return envelope(0, "ok", {"agent": agent_status, "java": java_status})
```

- [ ] **Step 9: 运行测试确认通过**

Run: `python -m pytest agent/tests/test_main_routes.py -v`
Expected: PASS（3 个测试全部通过；注意 `/health` 测试里 java_status 因没有真实 Java 服务会走 `except` 分支返回 `{"status": "unavailable"}`，`"status" in body["data"]` 断言的是顶层不存在但 `"java"` 一定存在，故用 `or` 兼容两种断言写法——测试按 Step 6 所写即可通过）

- [ ] **Step 10: Commit**

```bash
git add agent/__init__.py agent/envelope.py agent/main.py agent/tests/test_envelope.py agent/tests/test_main_routes.py
git commit -m "feat(agent): 加 main.py FastAPI入口+路由+信封响应+全局异常处理"
```

---

## Task 10: `web/` 前端脚手架 —— Vite + Vue3 + TS 项目初始化

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/index.html`
- Create: `web/src/main.ts`
- Create: `web/src/App.vue`
- Create: `web/src/router/index.ts`
- Create: `web/.gitignore`

**Interfaces:**
- Produces: 可通过 `npm run dev` 启动的空壳 Vue3 应用，路由挂载三个占位路径 `/findbook`、`/knowledge`、`/seat`（组件在 Task 11-13 补齐前先用内联占位组件，避免此任务因组件未写而无法启动）

- [ ] **Step 1: 写 `web/package.json`**

```json
{
  "name": "library-patch-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "1.7.7",
    "echarts": "5.5.1",
    "vue": "3.5.12",
    "vue-router": "4.4.5"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "5.1.4",
    "typescript": "5.6.3",
    "vite": "5.4.10",
    "vue-tsc": "2.1.10"
  }
}
```

- [ ] **Step 2: 写 `web/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
  },
});
```

- [ ] **Step 3: 写 `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM"],
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

- [ ] **Step 4: 写 `web/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>图书馆补丁</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: 写 `web/src/main.ts`**

```typescript
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

createApp(App).use(router).mount("#app");
```

- [ ] **Step 6: 写 `web/src/router/index.ts`**（占位组件，Task 11-13 会替换成真实视图）

```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/findbook" },
  { path: "/findbook", component: () => import("../views/FindBookView.vue") },
  { path: "/knowledge", component: () => import("../views/KnowledgeMapView.vue") },
  { path: "/seat", component: () => import("../views/SeatPredictView.vue") },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
```

- [ ] **Step 7: 写 `web/src/App.vue`**

```vue
<script setup lang="ts">
</script>

<template>
  <nav class="nav">
    <RouterLink to="/findbook">找书</RouterLink>
    <RouterLink to="/knowledge">知识地图</RouterLink>
    <RouterLink to="/seat">座位预测</RouterLink>
  </nav>
  <main>
    <RouterView />
  </main>
</template>

<style>
.nav {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-bottom: 1px solid #ddd;
}
</style>
```

- [ ] **Step 8: 写 `web/.gitignore`**

```
node_modules/
dist/
.env.local
```

- [ ] **Step 9: 建最小占位视图，让项目能启动（后续任务会替换为完整实现）**

创建 `web/src/views/FindBookView.vue`、`web/src/views/KnowledgeMapView.vue`、`web/src/views/SeatPredictView.vue`，每个内容如下（以 FindBookView.vue 为例，其余两个把文字替换成对应功能名）：

```vue
<script setup lang="ts">
</script>

<template>
  <div>找书页面占位，Task 11 将实现完整功能</div>
</template>
```

- [ ] **Step 10: 安装依赖并验证启动**

Run: `cd web && npm install && npm run dev`
Expected: 终端输出 `Local: http://localhost:5173/`，手动用浏览器打开确认导航栏 3 个链接可切换且不报错，然后 `Ctrl+C` 停止

- [ ] **Step 11: Commit**

```bash
git add web/package.json web/vite.config.ts web/tsconfig.json web/index.html web/src/main.ts web/src/App.vue web/src/router/index.ts web/.gitignore web/src/views/FindBookView.vue web/src/views/KnowledgeMapView.vue web/src/views/SeatPredictView.vue
git commit -m "feat(web): 初始化 Vue3+Vite+TS 项目脚手架 + 三页路由骨架"
```

---

## Task 11: `web/` API 层 —— client.ts + findbook.ts + knowledge.ts + seat.ts

**Files:**
- Create: `web/src/api/client.ts`
- Create: `web/src/api/findbook.ts`
- Create: `web/src/api/knowledge.ts`
- Create: `web/src/api/seat.ts`

**Interfaces:**
- Produces:
  - `web/src/api/client.ts`: `const http: AxiosInstance`（baseURL 从 `import.meta.env.VITE_AGENT_BASE_URL` 读取，缺省 `http://127.0.0.1:8000`；请求拦截器注入 `X-User-Id`）；`function mapErrorMessage(code: number): string`；`interface Envelope<T> { code: number; msg: string; data: T | null }`
  - `web/src/api/findbook.ts`: `async function searchBooks(query: string, page: number, pageSize: number): Promise<...>`；`async function sendFeedback(feedback: string): Promise<string[]>`
  - `web/src/api/knowledge.ts`: `async function buildGraph(paperId: string)`；`async function summarizePaper(paperId: string)`
  - `web/src/api/seat.ts`: `async function predictSeats(weekday: number, hour: number)`；`async function sendFeedback(feedback: string)`

- [ ] **Step 1: 写 `web/src/api/client.ts`**

```typescript
import axios, { type AxiosInstance } from "axios";

export interface Envelope<T> {
  code: number;
  msg: string;
  data: T | null;
}

const USER_ID_KEY = "library-patch-user-id";

function getUserId(): string {
  const existing = localStorage.getItem(USER_ID_KEY);
  if (existing) return existing;
  localStorage.setItem(USER_ID_KEY, "default");
  return "default";
}

export const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_AGENT_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 10000,
});

http.interceptors.request.use((request) => {
  request.headers["X-User-Id"] = getUserId();
  return request;
});

const ERROR_MESSAGES: Record<number, string> = {
  50001: "图书馆数据服务暂时不可用，请稍后再试",
  50002: "图书馆数据服务暂时不可用，请稍后再试",
  60001: "AI 助手暂时无法使用，已为你展示基础结果",
  60002: "偏好记忆服务异常，本次结果可能未个性化",
};

export function mapErrorMessage(code: number): string {
  if (code === 0) return "";
  return ERROR_MESSAGES[code] ?? "出了点问题，请稍后再试";
}

export async function unwrap<T>(promise: Promise<{ data: Envelope<T> }>): Promise<T> {
  const response = await promise;
  const envelope = response.data;
  if (envelope.code !== 0) {
    throw new Error(mapErrorMessage(envelope.code));
  }
  return envelope.data as T;
}
```

- [ ] **Step 2: 写 `web/src/api/findbook.ts`**

```typescript
import { http, unwrap } from "./client";

export interface Holding {
  callNo: string;
  location: string;
  status: string;
  available: boolean;
  barCode: string;
}

export interface Book {
  bibId: string;
  title: string;
  author: string;
  publisher: string;
  pubYear: string;
  isbn: string;
  classNo: string;
  callNos: string[];
  abstract: string;
  holdings: Holding[];
}

export interface FindBookResult {
  total: number;
  page: number;
  pageSize: number;
  books: Book[];
}

export async function searchBooks(query: string, page = 1, pageSize = 10): Promise<FindBookResult> {
  return unwrap(http.post("/findbook/search", { query, page, page_size: pageSize }));
}

export async function sendFeedback(feedback: string): Promise<string[]> {
  const result = await unwrap<{ memory_ids: string[] }>(http.post("/findbook/feedback", { feedback }));
  return result.memory_ids;
}
```

- [ ] **Step 3: 写 `web/src/api/knowledge.ts`**

```typescript
import { http, unwrap } from "./client";

export interface GraphNode {
  paperId: string;
  title?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface CitationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export async function buildGraph(paperId: string): Promise<CitationGraph> {
  return unwrap(http.post("/knowledge/graph", { paper_id: paperId }));
}

export async function summarizePaper(paperId: string): Promise<Record<string, unknown>> {
  return unwrap(http.post("/knowledge/summarize", { paper_id: paperId }));
}
```

- [ ] **Step 4: 写 `web/src/api/seat.ts`**

```typescript
import { http, unwrap } from "./client";

export interface SeatRankingItem {
  area_name: string;
  avg_occupancy_rate: number;
}

export interface SeatPrediction {
  ranking: SeatRankingItem[];
  realtime_available: boolean;
}

export async function predictSeats(weekday: number, hour: number): Promise<SeatPrediction> {
  return unwrap(http.post("/seat/predict", { weekday, hour }));
}

export async function sendFeedback(feedback: string): Promise<string[]> {
  const result = await unwrap<{ memory_ids: string[] }>(http.post("/seat/feedback", { feedback }));
  return result.memory_ids;
}
```

- [ ] **Step 5: 手动验证类型检查通过**

Run: `cd web && npx vue-tsc --noEmit`
Expected: 无类型错误输出（若报 `import.meta.env` 类型错误，在 `web/tsconfig.json` 的 `include` 里确认 `vite/client` 类型已随 vite 依赖自动可用；正常情况下 vite 5.x 项目无需额外配置）

- [ ] **Step 6: Commit**

```bash
git add web/src/api/client.ts web/src/api/findbook.ts web/src/api/knowledge.ts web/src/api/seat.ts
git commit -m "feat(web): 加 API 层(axios封装+信封解包+错误文案映射)"
```

---

## Task 12: `web/` 共享组件 —— FeedbackBox / LoadingState / ErrorState

**Files:**
- Create: `web/src/components/FeedbackBox.vue`
- Create: `web/src/components/LoadingState.vue`
- Create: `web/src/components/ErrorState.vue`

**Interfaces:**
- Produces:
  - `FeedbackBox.vue`：props `{ onSubmit: (text: string) => Promise<void> }`；内部渲染 👍/👎 按钮 + 文本框 + 提交按钮，点击后调用 `onSubmit`，成功后显示"已记录，谢谢反馈"提示 3 秒后消失
  - `LoadingState.vue`：无 props，渲染统一的加载中提示
  - `ErrorState.vue`：props `{ message: string }`，渲染统一的错误提示样式

- [ ] **Step 1: 写 `web/src/components/LoadingState.vue`**

```vue
<script setup lang="ts">
</script>

<template>
  <div class="loading-state" role="status" aria-live="polite">加载中…</div>
</template>

<style scoped>
.loading-state {
  padding: 2rem;
  text-align: center;
  color: #666;
}
</style>
```

- [ ] **Step 2: 写 `web/src/components/ErrorState.vue`**

```vue
<script setup lang="ts">
defineProps<{ message: string }>();
</script>

<template>
  <div class="error-state" role="alert">{{ message }}</div>
</template>

<style scoped>
.error-state {
  padding: 1rem;
  border: 1px solid #e57373;
  background: #fdecea;
  color: #b71c1c;
  border-radius: 4px;
}
</style>
```

- [ ] **Step 3: 写 `web/src/components/FeedbackBox.vue`**

```vue
<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ onSubmit: (text: string) => Promise<void> }>();

const text = ref("");
const submitted = ref(false);
const submitting = ref(false);
const errorMessage = ref("");

async function submit(prefix: string) {
  const feedbackText = prefix ? `${prefix}${text.value}` : text.value;
  if (!feedbackText.trim()) return;
  submitting.value = true;
  errorMessage.value = "";
  try {
    await props.onSubmit(feedbackText);
    submitted.value = true;
    text.value = "";
    setTimeout(() => {
      submitted.value = false;
    }, 3000);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "反馈提交失败，请稍后再试";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="feedback-box">
    <div class="feedback-buttons">
      <button type="button" :disabled="submitting" @click="submit('赞:')">👍</button>
      <button type="button" :disabled="submitting" @click="submit('差评:')">👎</button>
    </div>
    <textarea v-model="text" placeholder="补充说明(可选)" rows="2" />
    <button type="button" :disabled="submitting" @click="submit('')">提交反馈</button>
    <p v-if="submitted" class="feedback-success">已记录，谢谢反馈</p>
    <p v-if="errorMessage" class="feedback-error">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
.feedback-box {
  margin-top: 1rem;
  padding: 0.75rem;
  border-top: 1px solid #eee;
}
.feedback-buttons {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.feedback-success {
  color: #2e7d32;
}
.feedback-error {
  color: #b71c1c;
}
</style>
```

- [ ] **Step 4: 手动验证类型检查通过**

Run: `cd web && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: Commit**

```bash
git add web/src/components/FeedbackBox.vue web/src/components/LoadingState.vue web/src/components/ErrorState.vue
git commit -m "feat(web): 加共享组件 FeedbackBox/LoadingState/ErrorState"
```

---

## Task 13: `web/` 三个功能视图 —— FindBookView / KnowledgeMapView / SeatPredictView

**Files:**
- Modify: `web/src/views/FindBookView.vue`（替换 Task 10 的占位内容）
- Modify: `web/src/views/KnowledgeMapView.vue`（替换 Task 10 的占位内容）
- Modify: `web/src/views/SeatPredictView.vue`（替换 Task 10 的占位内容）

**Interfaces:**
- Consumes:
  - `web/src/api/findbook.ts`：`searchBooks`, `sendFeedback`, 类型 `FindBookResult`, `Book`（Task 11）
  - `web/src/api/knowledge.ts`：`buildGraph`, `summarizePaper`, 类型 `CitationGraph`（Task 11）
  - `web/src/api/seat.ts`：`predictSeats`, `sendFeedback`, 类型 `SeatPrediction`（Task 11）
  - `web/src/components/{FeedbackBox,LoadingState,ErrorState}.vue`（Task 12）
  - `echarts`（package.json 已声明依赖，Task 10）

- [ ] **Step 1: 写 `web/src/views/FindBookView.vue`**

```vue
<script setup lang="ts">
import { ref } from "vue";
import { searchBooks, sendFeedback, type FindBookResult } from "../api/findbook";
import ErrorState from "../components/ErrorState.vue";
import FeedbackBox from "../components/FeedbackBox.vue";
import LoadingState from "../components/LoadingState.vue";

const query = ref("");
const result = ref<FindBookResult | null>(null);
const loading = ref(false);
const errorMessage = ref("");

async function search() {
  if (!query.value.trim()) return;
  loading.value = true;
  errorMessage.value = "";
  result.value = null;
  try {
    result.value = await searchBooks(query.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  await sendFeedback(text);
}
</script>

<template>
  <section class="findbook">
    <h1>找书</h1>
    <form @submit.prevent="search">
      <input v-model="query" type="text" placeholder="输入书名/作者/关键词" />
      <button type="submit">搜索</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />
    <ul v-else-if="result" class="book-list">
      <li v-for="book in result.books" :key="book.bibId" class="book-card">
        <h2>{{ book.title }}</h2>
        <p>{{ book.author }} · {{ book.publisher }} · {{ book.pubYear }}</p>
        <ul>
          <li v-for="holding in book.holdings" :key="holding.barCode">
            {{ holding.callNo }} · {{ holding.location }} ·
            <strong>{{ holding.status }}</strong>
          </li>
        </ul>
      </li>
    </ul>

    <FeedbackBox :on-submit="submitFeedback" />
  </section>
</template>

<style scoped>
.book-card {
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 0.75rem;
  margin-bottom: 0.75rem;
}
</style>
```

- [ ] **Step 2: 写 `web/src/views/KnowledgeMapView.vue`**

```vue
<script setup lang="ts">
import * as echarts from "echarts";
import { nextTick, ref } from "vue";
import { buildGraph, summarizePaper } from "../api/knowledge";
import ErrorState from "../components/ErrorState.vue";
import FeedbackBox from "../components/FeedbackBox.vue";
import LoadingState from "../components/LoadingState.vue";

const paperId = ref("");
const loading = ref(false);
const errorMessage = ref("");
const summary = ref<Record<string, unknown> | null>(null);
const chartContainer = ref<HTMLDivElement | null>(null);

async function loadGraph() {
  if (!paperId.value.trim()) return;
  loading.value = true;
  errorMessage.value = "";
  summary.value = null;
  try {
    const graph = await buildGraph(paperId.value);
    await nextTick();
    if (chartContainer.value) {
      const chart = echarts.init(chartContainer.value);
      chart.setOption({
        series: [
          {
            type: "graph",
            layout: "force",
            data: graph.nodes.map((n) => ({ id: n.paperId, name: n.title ?? n.paperId })),
            links: graph.edges.map((e) => ({ source: e.source, target: e.target })),
          },
        ],
      });
    }
    summary.value = await summarizePaper(paperId.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  // 知识地图暂无独立反馈接口，走通用 /memory/feedback 契约兜底入口
  const { http, unwrap } = await import("../api/client");
  await unwrap(http.post("/memory/feedback", { feedback: text, task_context: `知识地图:${paperId.value}` }));
}
</script>

<template>
  <section class="knowledge-map">
    <h1>知识地图</h1>
    <form @submit.prevent="loadGraph">
      <input v-model="paperId" type="text" placeholder="输入论文 paperId" />
      <button type="submit">构建引用图</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />
    <div v-else ref="chartContainer" class="chart" style="width: 100%; height: 400px"></div>

    <div v-if="summary" class="summary">
      <h2>摘要</h2>
      <pre>{{ summary }}</pre>
    </div>

    <FeedbackBox :on-submit="submitFeedback" />
  </section>
</template>
```

- [ ] **Step 3: 写 `web/src/views/SeatPredictView.vue`**

```vue
<script setup lang="ts">
import * as echarts from "echarts";
import { nextTick, ref } from "vue";
import { predictSeats, sendFeedback } from "../api/seat";
import ErrorState from "../components/ErrorState.vue";
import FeedbackBox from "../components/FeedbackBox.vue";
import LoadingState from "../components/LoadingState.vue";

const weekday = ref(1);
const hour = ref(14);
const loading = ref(false);
const errorMessage = ref("");
const realtimeAvailable = ref(true);
const chartContainer = ref<HTMLDivElement | null>(null);

async function predict() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const prediction = await predictSeats(weekday.value, hour.value);
    realtimeAvailable.value = prediction.realtime_available;
    await nextTick();
    if (chartContainer.value) {
      const chart = echarts.init(chartContainer.value);
      chart.setOption({
        xAxis: { type: "category", data: prediction.ranking.map((r) => r.area_name) },
        yAxis: { type: "value", name: "占用率" },
        series: [
          {
            type: "bar",
            data: prediction.ranking.map((r) => Math.round(r.avg_occupancy_rate * 100)),
          },
        ],
      });
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  await sendFeedback(text);
}
</script>

<template>
  <section class="seat-predict">
    <h1>座位预测</h1>
    <form @submit.prevent="predict">
      <label>
        星期
        <select v-model.number="weekday">
          <option v-for="d in 7" :key="d" :value="d">{{ d }}</option>
        </select>
      </label>
      <label>
        时段
        <input v-model.number="hour" type="number" min="0" max="23" />
      </label>
      <button type="submit">预测</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />
    <template v-else>
      <p v-if="!realtimeAvailable" class="realtime-hint">
        实时占用数据暂不可用，以下为历史平均占用率
      </p>
      <div ref="chartContainer" class="chart" style="width: 100%; height: 300px"></div>
    </template>

    <FeedbackBox :on-submit="submitFeedback" />
  </section>
</template>

<style scoped>
.realtime-hint {
  color: #ef6c00;
}
</style>
```

- [ ] **Step 4: 手动验证类型检查通过**

Run: `cd web && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: 手动启动验证三页可用**

Run: `cd web && npm run dev`
Expected: 打开 `http://localhost:5173/findbook`、`/knowledge`、`/seat` 三页均能正常渲染表单（此时后端 agent 未必已启动，提交后预期看到 ErrorState 展示的人话错误文案，而不是白屏或裸控制台报错），确认后 `Ctrl+C` 停止

- [ ] **Step 6: Commit**

```bash
git add web/src/views/FindBookView.vue web/src/views/KnowledgeMapView.vue web/src/views/SeatPredictView.vue
git commit -m "feat(web): 实现三功能视图(找书结果卡片/知识图谱ECharts/座位占用条形图)"
```

---

## Task 14: 端到端联调准备 + 计划自查

**Files:**
- 无新文件；核对已完成任务

- [ ] **Step 1: 全量运行 Python 测试套件**

Run: `python -m pytest agent/tests -v`
Expected: 除 `test_main_routes.py` 外全部 PASS（`test_main_routes.py` 用 dependency-override 规避了 B 未交付的问题，应同样 PASS）；若某个测试因为路径问题报 `ModuleNotFoundError: No module named 'agent'`，检查是否从仓库根目录执行命令

- [ ] **Step 2: 确认未越界修改 A/B 目录**

Run: `git status --short service/ agent/core/ agent/memory/ collector/`
Expected: 无任何输出（这四个目录下没有本计划引入的改动）

- [ ] **Step 3: 记录已知限制到 README 或交给团队的说明（不修改 A/B 段落，只追加 C 的部分）**

在 `README.md` 末尾（若已有类似"当前状态"章节则追加在其下，否则新增一节）追加：

```markdown
## C 角色（粘合侧）当前状态

- `agent/main.py`、`service_client.py`、三个 `features/*`、`benchmark/harness.py`、`web/` 已按接口契约实现并有测试覆盖。
- `main.py` 中 `from agent.core.agent_loop import AgentLoop` 依赖 B 交付，B 完成前 `main.py` 无法真正启动（`agent/tests/` 下的单测通过依赖注入/替身规避此限制，已验证业务逻辑正确）。
- `seat_predict/service.py` 假定 `seats.db` 存在表 `seat_snapshots(weekday, hour, area_name, occupied, total)`，此 schema 待与 A 确认；若字段不同，只需改 `agent/features/seat_predict/service.py` 中的一处 SQL。
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: 追加 C 角色当前状态说明(main.py依赖B交付 + seat_snapshots schema待确认)"
```

---

## Self-Review Notes

- **Spec coverage**：spec 第4-11节（service_client / findbook / knowledge_map / seat_predict / benchmark / main.py+共享文件 / web）分别对应 Task 1、3-9、10-13；第3节的 mock 策略贯穿 Task 2（FakeAgentLoop）与各 Task 的 httpx.MockTransport 用法；第12节"明确不做"未产出任何任务，符合预期。
- **Placeholder scan**：已核对，无 TBD/"类似 Task N"/无代码块的步骤。
- **Type consistency**：`AgentResult`/`FakeAgentResult` 字段名（`feature/output/memories_used/elapsed_ms/tokens/plan_note/used_llm/trace_id`）在 Task 2、4、6、7、8、9 中保持一致；`ServiceError`/`ServiceUnavailable` 在 Task 3 定义后被 Task 4、7、9 原样引用；前端 `Envelope<T>`/`unwrap` 在 Task 11 定义后被 Task 13 一致使用。
