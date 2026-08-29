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
        assert request.url.path == "/graph/v1/paper/search"
        return httpx.Response(200, json={"data": [{"paperId": "p1", "title": "A"}]})

    client = _client(handler, monkeypatch)
    results = await client.search("attention is all you need", limit=5)
    assert results == [{"paperId": "p1", "title": "A"}]


@pytest.mark.asyncio
async def test_paper_returns_single_dict(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/v1/paper/p1"
        return httpx.Response(200, json={"paperId": "p1", "title": "A"})

    client = _client(handler, monkeypatch)
    result = await client.paper("p1")
    assert result == {"paperId": "p1", "title": "A"}


@pytest.mark.asyncio
async def test_references_flattens_cited_paper(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/v1/paper/p1/references"
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
