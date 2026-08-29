"""B 模块 · 核心内核单元测试。

覆盖：
- llm: LLMClient.available / Usage 默认值 / 无 key 调 complete 报错
- planner: 无 key 透传 / 无记忆透传 / 有记忆精炼 / LLM 异常降级
- extractor: JSON mode + pydantic 校验 / 失败重试一次 / 两次失败丢弃 / 无 key 空
- agent_loop: query_key 精炼 / 无记忆透传 / trace_id 透传与新建
- record_feedback: 反馈入环 / 幂等 / 无 LLM
"""
import pytest

from agent.core.agent_loop import AgentLoop, AgentResult
from agent.core.llm import LLMClient, Usage
from agent.core.planner import Planner
from agent.memory.extractor import MemoryExtractor
from agent.memory.models import MemoryEntry
from agent.memory.retriever import MemoryRetriever
from agent.memory.store import MemoryStore


class FakeLLM:
    """测试替身：模拟 LLMClient 的 available / complete_json 接口，不碰网络。"""

    def __init__(self, available=True, json=None, error=None, tokens=10):
        self._available = available
        self._json = json if json is not None else {}
        self._error = error
        self._tokens = tokens
        self.last_usage = Usage()
        self.json_calls = 0

    @property
    def available(self):
        return self._available

    async def complete_json(self, messages, **kw):
        self.json_calls += 1
        if self._error:
            raise self._error
        self.last_usage = Usage(total_tokens=self._tokens)
        if isinstance(self._json, list):
            return self._json.pop(0) if self._json else {}
        return self._json


def build_loop(planner_llm=None, extractor_llm=None, entries=None):
    store = MemoryStore(":memory:")
    for e in entries or []:
        store.add(e)
    retriever = MemoryRetriever(store)
    planner = Planner(planner_llm or FakeLLM(available=False))
    extractor = MemoryExtractor(extractor_llm or FakeLLM(available=False))
    loop = AgentLoop(retriever=retriever, planner=planner, store=store, extractor=extractor)
    return loop, store


# ---------- llm ----------


def test_llm_available():
    assert LLMClient(base_url="", api_key="", model="").available is False
    assert LLMClient(base_url="http://x", api_key="k", model="m").available is True


def test_usage_defaults():
    u = Usage()
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (0, 0, 0)


@pytest.mark.asyncio
async def test_complete_without_key_raises():
    c = LLMClient(base_url="", api_key="", model="")
    with pytest.raises(RuntimeError):
        await c.complete([{"role": "user", "content": "hi"}])


# ---------- planner ----------


@pytest.mark.asyncio
async def test_planner_passthrough_no_key():
    p = Planner(FakeLLM(available=False))
    r = await p.plan("找书", "找机器学习的书", "机器学习", "【用户记忆】\n- 只要近五年的书")
    assert r.query == "机器学习"
    assert r.used_llm is False
    assert r.note == ""


@pytest.mark.asyncio
async def test_planner_passthrough_no_memory():
    p = Planner(FakeLLM(available=True))
    r = await p.plan("找书", "找机器学习的书", "机器学习", "")
    assert r.query == "机器学习"
    assert r.used_llm is False


@pytest.mark.asyncio
async def test_planner_refines_with_memory():
    p = Planner(FakeLLM(json={"query": "机器学习 2019-2024", "note": "已按偏好只找近五年"}))
    r = await p.plan("找书", "找机器学习的书", "机器学习", "【用户记忆】\n- 只要近五年的书")
    assert r.query == "机器学习 2019-2024"
    assert r.note == "已按偏好只找近五年"
    assert r.used_llm is True
    assert r.usage.total_tokens == 10


@pytest.mark.asyncio
async def test_planner_degrades_on_error():
    p = Planner(FakeLLM(error=RuntimeError("boom")))
    r = await p.plan("找书", "找机器学习的书", "机器学习", "【用户记忆】\n- 只要近五年的书")
    assert r.query == "机器学习"
    assert r.used_llm is False


# ---------- extractor ----------


@pytest.mark.asyncio
async def test_extractor_no_llm_returns_empty():
    ex = MemoryExtractor(FakeLLM(available=False))
    entries = await ex.extract("我喜欢靠窗", "u1", subject="找书")
    assert entries == []


@pytest.mark.asyncio
async def test_extractor_retries_once_then_succeeds():
    llm = FakeLLM(json=[
        {"memories": [{"content": ""}]},         # 非法: content 为空 → 校验失败
        {"memories": [{"content": "喜欢靠窗"}]},  # 合法
    ])
    ex = MemoryExtractor(llm)
    entries = await ex.extract("我喜欢靠窗", "u1", subject="找书")
    assert len(entries) == 1
    assert entries[0].content == "喜欢靠窗"
    assert llm.json_calls == 2


@pytest.mark.asyncio
async def test_extractor_discards_after_two_failures():
    llm = FakeLLM(json=[
        {"memories": [{"content": ""}]},
        {"memories": [{"content": ""}]},
    ])
    ex = MemoryExtractor(llm)
    entries = await ex.extract("x", "u1", subject="找书")
    assert entries == []
    assert llm.json_calls == 2


# ---------- agent_loop ----------


@pytest.mark.asyncio
async def test_agent_loop_query_key_refines():
    entry = MemoryEntry(user_id="u1", type="rule", subject="找书", content="只要近五年的书", confidence=0.9)
    planner_llm = FakeLLM(json={"query": "机器学习 2019-2024", "note": "已按偏好只找近五年"})
    loop, store = build_loop(planner_llm=planner_llm, entries=[entry])

    seen = {}

    async def tool(args):
        seen.update(args)
        return {"ok": True}

    loop.register_tool("search_books", tool)
    result = await loop.run(
        feature="findbook", subject="找书", task="找机器学习的书",
        tool_name="search_books", tool_args={"query": "机器学习"},
        user_id="u1", trace_id="", query_key="query",
    )
    assert seen["query"] == "机器学习 2019-2024"
    assert result.used_llm is True
    assert result.memories_used == [entry.entry_id]
    assert result.plan_note == "已按偏好只找近五年"
    assert result.output == {"ok": True}
    assert result.trace_id


@pytest.mark.asyncio
async def test_agent_loop_query_key_passthrough_no_memory():
    planner_llm = FakeLLM(json={"query": "X", "note": "n"})
    loop, store = build_loop(planner_llm=planner_llm, entries=[])

    seen = {}

    async def tool(args):
        seen.update(args)
        return "done"

    loop.register_tool("search_books", tool)
    result = await loop.run(
        feature="findbook", subject="找书", task="t",
        tool_name="search_books", tool_args={"query": "机器学习"},
        user_id="u1", trace_id="", query_key="query",
    )
    assert seen["query"] == "机器学习"
    assert result.used_llm is False
    assert result.memories_used == []


@pytest.mark.asyncio
async def test_agent_loop_trace_id():
    loop, store = build_loop()

    async def tool(args):
        return None

    loop.register_tool("t", tool)
    r1 = await loop.run(feature="f", subject="s", task="t", tool_name="t", tool_args={},
                        user_id="u1", trace_id="a1b2c3d4")
    assert r1.trace_id == "a1b2c3d4"
    r2 = await loop.run(feature="f", subject="s", task="t", tool_name="t", tool_args={},
                        user_id="u1", trace_id="")
    assert len(r2.trace_id) == 8
    assert all(c in "0123456789abcdef" for c in r2.trace_id)


# ---------- record_feedback ----------


@pytest.mark.asyncio
async def test_record_feedback_extracts_and_stores():
    extractor_llm = FakeLLM(json={"memories": [
        {"type": "preference", "subject": "找书", "content": "喜欢靠窗", "confidence": 0.9},
    ]})
    loop, store = build_loop(extractor_llm=extractor_llm)
    ids = await loop.record_feedback("我喜欢靠窗的座位", "u1", task_context="找书:机器学习")
    assert len(ids) == 1
    entries = store.query("u1")
    assert len(entries) == 1
    assert entries[0].content == "喜欢靠窗"
    assert entries[0].subject == "找书"


@pytest.mark.asyncio
async def test_record_feedback_idempotent():
    extractor_llm = FakeLLM(json={"memories": [{"content": "喜欢靠窗"}]})
    loop, store = build_loop(extractor_llm=extractor_llm)
    ids1 = await loop.record_feedback("我喜欢靠窗", "u1")
    ids2 = await loop.record_feedback("我喜欢靠窗", "u1")
    assert ids1 == ids2
    assert extractor_llm.json_calls == 1  # 第二次命中反馈级缓存，不再抽取
    assert len(store.query("u1")) == 1


@pytest.mark.asyncio
async def test_record_feedback_no_llm():
    loop, store = build_loop(extractor_llm=FakeLLM(available=False))
    ids = await loop.record_feedback("我喜欢靠窗", "u1")
    assert ids == []
    assert store.query("u1") == []
