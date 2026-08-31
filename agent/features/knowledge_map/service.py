"""P1 知识地图功能。build_citation_graph 工具不需要 LLM，直接组装引用图；
summarize_paper 工具只取回原始论文数据交给 planner/LLM 生成摘要
(是否调用 LLM 是 agent_loop 内部的事，本类不关心)。

S2 公共端点限流狠(429), 重试耗尽后降级为带 error 的结果, 绝不抛 500 堆栈。
"""
from __future__ import annotations

import asyncio

import httpx

_S2_ERROR_MSG = "Semantic Scholar 暂时不可用（可能限流），请稍后重试"
_FIRST_LEVEL_LIMIT = 20
_SECOND_LEVEL_LIMIT = 5
_SECOND_LEVEL_PARENTS = 12
_SECOND_LEVEL_CONCURRENCY = 3


class KnowledgeMapService:
    def __init__(self, agent_loop, s2_client, s2_cache):
        self._agent_loop = agent_loop
        self._s2 = s2_client
        self._cache = s2_cache
        self._agent_loop.register_tool("build_citation_graph", self._build_graph_tool)
        self._agent_loop.register_tool("summarize_paper", self._summarize_tool)

    async def _build_graph_tool(self, tool_args: dict) -> dict:
        paper_id = tool_args["paper_id"]
        try:
            first_level = await self._references(paper_id, _FIRST_LEVEL_LIMIT)
        except httpx.HTTPError:
            return {"nodes": [], "edges": [], "error": _S2_ERROR_MSG}

        try:
            center = await self._paper(paper_id)
        except httpx.HTTPError:
            center = {"paperId": paper_id}
        nodes_by_id: dict[str, dict] = {
            paper_id: {**center, "paperId": paper_id, "depth": 0}
        }
        edges_by_key: dict[tuple[str, str], dict] = {}

        valid_first = [item for item in first_level if item.get("paperId")]
        for item in valid_first:
            child_id = item["paperId"]
            nodes_by_id.setdefault(child_id, {**item, "depth": 1})
            edges_by_key[(paper_id, child_id)] = {
                "source": paper_id, "target": child_id, "depth": 1,
            }

        # 第二层只展开部分一级分支并限制并发，避免公共 API 瞬时触发 429。
        semaphore = asyncio.Semaphore(_SECOND_LEVEL_CONCURRENCY)

        async def fetch_second(parent: dict) -> tuple[str, list[dict]]:
            parent_id = parent["paperId"]
            async with semaphore:
                try:
                    return parent_id, await self._references(parent_id, _SECOND_LEVEL_LIMIT)
                except httpx.HTTPError:
                    return parent_id, []  # 单个分支失败时保留其余图谱

        branches = await asyncio.gather(
            *(fetch_second(item) for item in valid_first[:_SECOND_LEVEL_PARENTS])
        )
        for parent_id, second_level in branches:
            for item in second_level:
                child_id = item.get("paperId")
                if not child_id or child_id == parent_id:
                    continue
                nodes_by_id.setdefault(child_id, {**item, "depth": 2})
                edges_by_key[(parent_id, child_id)] = {
                    "source": parent_id, "target": child_id, "depth": 2,
                }

        return {
            "nodes": list(nodes_by_id.values()),
            "edges": list(edges_by_key.values()),
            "maxDepth": 2,
        }

    async def _references(self, paper_id: str, limit: int) -> list[dict]:
        cache_key = f"references:v2:{paper_id}:limit:{limit}"
        cited = self._cache.get(cache_key)
        if cited is None:
            cited = await self._s2.references(paper_id, limit=limit)
            self._cache.set(cache_key, cited)
        return cited

    async def _paper(self, paper_id: str) -> dict:
        cache_key = f"paper:v2:{paper_id}"
        detail = self._cache.get(cache_key)
        if detail is None:
            detail = await self._s2.paper(paper_id)
            self._cache.set(cache_key, detail)
        return detail

    async def _summarize_tool(self, tool_args: dict) -> dict:
        paper_id = tool_args["paper_id"]
        try:
            detail = await self._paper(paper_id)
        except httpx.HTTPError:
            return {"error": _S2_ERROR_MSG}
        return detail

    async def search_papers(self, query: str, limit: int = 8) -> dict:
        """关键词找论文(用户不知道 paperId 时的入口)。限流降级为空列表+error。"""
        try:
            results = await self._s2.search(query, limit=limit)
        except httpx.HTTPError:
            return {"papers": [], "error": _S2_ERROR_MSG}
        return {"papers": results}

    async def build_graph(self, paper_id: str, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="knowledge_map",
            subject="知识地图",
            task=f"构建引用图: {paper_id}",
            tool_name="build_citation_graph",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )

    async def summarize(self, paper_id: str, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="knowledge_map",
            subject="知识地图",
            task=f"摘要: {paper_id}",
            tool_name="summarize_paper",
            tool_args={"paper_id": paper_id, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )
