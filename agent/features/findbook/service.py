"""P0 找书功能。注册 search_books 工具给 AgentLoop(契约②)，通过依赖注入
持有 agent_loop 与 service_client，不在模块顶层导入全局单例。
"""
from __future__ import annotations

from agent.service_client import ServiceError, ServiceUnavailable


class FindBookService:
    def __init__(self, agent_loop, service_client):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._agent_loop.register_tool("search_books", self._search_books_tool)

    async def _search_books_tool(self, query: str, page: int, page_size: int, trace_id: str) -> dict:
        try:
            return await self._service_client.search_books(query, page, page_size, trace_id)
        except (ServiceError, ServiceUnavailable):
            return {"error": "图书检索服务暂时不可用，请稍后再试"}

    async def find(self, query: str, page: int, page_size: int, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="findbook",
            subject="找书",
            task=f"查询: {query}",
            tool_name="search_books",
            tool_args={"query": query, "page": page, "page_size": page_size, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key="query",
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"找书:{feedback[:30]}",
            trace_id=trace_id,
        )
