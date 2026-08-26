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
