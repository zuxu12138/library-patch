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


def test_findbook_search_missing_query_returns_422_not_500(client):
    """请求体校验: 缺 query 由 FastAPI 自动 422, 不再是 KeyError → 原生 500。"""
    response = client.post("/findbook/search", json={"page": 1})
    assert response.status_code == 422


def test_unexpected_error_returns_envelope_not_raw_500():
    """兜底处理器: 未预期异常也返回统一信封, 不漏技术栈给前端。"""
    loop = FakeAgentLoop()
    from agent.features.findbook.service import FindBookService

    class _BoomClient:
        async def search_books(self, query, page, page_size, trace_id):
            raise RuntimeError("unexpected sqlite locked")

    service = FindBookService(loop, _BoomClient())
    app.dependency_overrides[get_findbook_service] = lambda: service
    # raise_server_exceptions=False: 只验证响应信封, 不让 TestClient 把已处理的异常再抛出来
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/findbook/search",
            json={"query": "机器学习", "page": 1, "page_size": 10},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 50000
    assert "sqlite" not in body["msg"]  # 技术原文不外泄
