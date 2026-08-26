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
