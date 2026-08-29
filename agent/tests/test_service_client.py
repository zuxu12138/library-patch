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
