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
