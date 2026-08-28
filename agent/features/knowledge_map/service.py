"""P1 知识地图功能。build_citation_graph 工具不需要 LLM，直接组装引用图；
summarize_paper 工具只取回原始论文数据交给 planner/LLM 生成摘要
(是否调用 LLM 是 agent_loop 内部的事，本类不关心)。

S2 公共端点限流狠(429), 重试耗尽后降级为带 error 的结果, 绝不抛 500 堆栈。
"""
from __future__ import annotations

import httpx

_S2_ERROR_MSG = "Semantic Scholar 暂时不可用（可能限流），请稍后重试"


class KnowledgeMapService:
    def __init__(self, agent_loop, s2_client, s2_cache):
        self._agent_loop = agent_loop
        self._s2 = s2_client
        self._cache = s2_cache
        self._agent_loop.register_tool("build_citation_graph", self._build_graph_tool)
        self._agent_loop.register_tool("summarize_paper", self._summarize_tool)

    async def _build_graph_tool(self, tool_args: dict) -> dict:
        # AgentLoop 契约: handler 接收 tool_args(dict), 见 agent/core/agent_loop.py
        paper_id = tool_args["paper_id"]
        cache_key = f"references:{paper_id}"
        cited = self._cache.get(cache_key)
        if cited is None:
            try:
                cited = await self._s2.references(paper_id)
            except httpx.HTTPError:
                return {"nodes": [], "edges": [], "error": _S2_ERROR_MSG}
            self._cache.set(cache_key, cited)
        nodes = [{"paperId": paper_id}] + cited
        edges = [{"source": paper_id, "target": item["paperId"]} for item in cited]
        return {"nodes": nodes, "edges": edges}

    async def _summarize_tool(self, tool_args: dict) -> dict:
        paper_id = tool_args["paper_id"]
        cache_key = f"paper:{paper_id}"
        detail = self._cache.get(cache_key)
        if detail is None:
            try:
                detail = await self._s2.paper(paper_id)
            except httpx.HTTPError:
                return {"error": _S2_ERROR_MSG}
            self._cache.set(cache_key, detail)
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
