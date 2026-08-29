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
