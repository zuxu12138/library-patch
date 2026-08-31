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
        if paper_id == "p1":
            return self.references_result
        if paper_id == "p2":
            return [{"paperId": "p3", "title": "C"}]
        return []

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
    assert result.output["maxDepth"] == 2
    assert {"source": "p2", "target": "p3", "depth": 2} in result.output["edges"]
    assert s2.reference_calls == ["p1", "p2"]


@pytest.mark.asyncio
async def test_build_graph_uses_cache_on_second_call(tmp_path):
    loop = FakeAgentLoop()
    s2 = _StubS2Client()
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    service = KnowledgeMapService(loop, s2, cache)

    await service.build_graph("p1", user_id="u1", trace_id="t1")
    await service.build_graph("p1", user_id="u1", trace_id="t2")

    assert s2.reference_calls == ["p1", "p2"]  # 第二次全部命中缓存，不再打 S2


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
