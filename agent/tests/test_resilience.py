"""本轮优化新增行为的回归测试:
- service_client 熔断器(连续失败短路 + 成功复位)
- retriever query_text 提权不扼杀(偏好记忆无字面重合也要召回)
- extractor 矛盾点名 + store.adjust_confidence 精准降权
"""
import pytest

from agent.core.agent_loop import AgentLoop
from agent.memory.extractor import MemoryExtractor
from agent.memory.models import MemoryEntry
from agent.memory.retriever import MemoryRetriever
from agent.memory.store import MemoryStore
from agent.service_client import ServiceClient, ServiceUnavailable


# ---------- 熔断器 ----------

class _FlakyTransport:
    """httpx MockTransport 不好模拟超时, 直接 stub request。"""

    def __init__(self):
        self.calls = 0

    def handle_async_request(self, request):
        self.calls += 1
        import httpx
        raise httpx.TimeoutException("boom")


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_consecutive_failures():
    import httpx

    transport = _FlakyTransport()
    client = ServiceClient(
        base_url="http://x",
        transport=httpx.MockTransport(transport.handle_async_request),
    )
    for _ in range(3):
        with pytest.raises(ServiceUnavailable):
            await client.health("t")
    calls_before = transport.calls
    # 熔断已打开: 冷却期内不再打下游
    with pytest.raises(ServiceUnavailable):
        await client.health("t")
    assert transport.calls == calls_before


# ---------- retriever: query_text 提权而非过滤 ----------

def _store() -> MemoryStore:
    return MemoryStore(":memory:")


def test_retriever_keeps_preference_without_textual_overlap():
    store = _store()
    # 偏好记忆与查询词无字面重合, 纯 FTS 过滤会错杀它
    store.add(MemoryEntry(user_id="u1", type="preference", subject="找书",
                          content="只要近五年出版的书"))
    store.add(MemoryEntry(user_id="u1", type="preference", subject="找书",
                          content="深度学习入门偏好图灵出品"))
    retriever = MemoryRetriever(store)

    results = retriever.retrieve(user_id="u1", subject="找书", query_text="深度学习")

    contents = [e.content for e in results]
    assert "深度学习入门偏好图灵出品" in contents          # 相关命中排前面
    assert "只要近五年出版的书" in contents                # 无字面重合也要保留
    assert contents[0] == "深度学习入门偏好图灵出品"        # 提权生效


# ---------- 精准冲突降权 ----------

class _FakeLLM:
    available = True
    last_usage = None

    def __init__(self, payload):
        self._payload = payload

    async def complete_json(self, messages, **kw):
        return self._payload


@pytest.mark.asyncio
async def test_contradiction_downgrades_only_named_memory():
    store = _store()
    old_conflict = MemoryEntry(user_id="u1", type="preference", subject="座位", content="喜欢靠窗")
    old_unrelated = MemoryEntry(user_id="u1", type="preference", subject="座位", content="喜欢安静")
    id_conflict = store.add(old_conflict)
    id_unrelated = store.add(old_unrelated)

    extractor = MemoryExtractor(_FakeLLM({
        "memories": [{"type": "preference", "subject": "座位", "content": "现在喜欢靠门",
                      "applies_to": "*", "confidence": 0.9}],
        "contradicts": [id_conflict],
    }))
    loop = AgentLoop(MemoryRetriever(store), planner=None, store=store, extractor=extractor)

    before_unrelated = store.get(id_unrelated).confidence
    ids = await loop.record_feedback("我现在喜欢靠门了", user_id="u1", task_context="座位纠错")

    assert len(ids) == 1
    assert store.get(id_conflict).confidence < 0.8        # 被点名的降权
    assert store.get(id_unrelated).confidence == before_unrelated  # 无辜的不动


@pytest.mark.asyncio
async def test_feedback_without_llm_stores_nothing_and_stays_honest():
    store = _store()
    extractor = MemoryExtractor(_FakeLLM({}))
    extractor.llm.available = False
    loop = AgentLoop(MemoryRetriever(store), planner=None, store=store, extractor=extractor)

    ids = await loop.record_feedback("我喜欢靠窗", user_id="u1")
    assert ids == []
    assert store.query("u1") == []


# ---------- S2 限流降级(不抛 500) ----------

class _RateLimitedS2:
    async def references(self, paper_id, limit=20):
        import httpx
        raise httpx.HTTPStatusError("429", request=None, response=None)

    async def paper(self, paper_id):
        import httpx
        raise httpx.HTTPStatusError("429", request=None, response=None)


@pytest.mark.asyncio
async def test_knowledge_map_degrades_on_s2_rate_limit(tmp_path):
    from agent.features.knowledge_map.s2_cache import S2Cache
    from agent.features.knowledge_map.service import KnowledgeMapService
    from agent.tests.fakes import FakeAgentLoop

    service = KnowledgeMapService(FakeAgentLoop(), _RateLimitedS2(),
                                  S2Cache(path=str(tmp_path / "c.json")))

    graph = await service.build_graph("p1", user_id="u1", trace_id="t")
    assert graph.output["nodes"] == []
    assert "error" in graph.output

    summary = await service.summarize("p1", user_id="u1", trace_id="t")
    assert "error" in summary.output
