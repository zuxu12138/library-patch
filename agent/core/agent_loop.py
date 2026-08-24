"""AgentLoop：检索记忆 → 规划注入 → 调工具 → 组装结果；反馈幂等入环。"""
from __future__ import annotations

import hashlib
import inspect
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentResult:
    feature: str
    output: Any
    memories_used: list
    elapsed_ms: float
    tokens: int
    plan_note: str
    used_llm: bool
    trace_id: str


class AgentLoop:
    def __init__(self, retriever, planner, store, extractor):
        self.retriever = retriever
        self.planner = planner
        self.store = store
        self.extractor = extractor
        self._tools: dict[str, Callable] = {}

    def register_tool(self, name: str, handler: Callable) -> None:
        """注册工具。handler 接收 tool_args(dict)，可同步可异步。"""
        self._tools[name] = handler

    @staticmethod
    def _new_trace_id() -> str:
        return secrets.token_hex(4)  # 8 位 hex

    async def run(
        self,
        feature: str,
        subject: str,
        task: str,
        tool_name: str,
        tool_args: dict,
        user_id: str,
        trace_id: str,
        query_key: str | None = None,
    ) -> AgentResult:
        trace_id = trace_id or self._new_trace_id()
        start = time.perf_counter()

        # 1) 检索记忆（user_id 隔离 + 功能范围过滤）
        memories = self.retriever.retrieve(user_id=user_id, subject=subject, applies_to=feature)
        memories_used = [m.entry_id for m in memories]

        tokens = 0
        used_llm = False
        plan_note = ""

        # 2) 规划（注入记忆精炼检索词）
        if query_key is not None and query_key in tool_args:
            block = self.retriever.to_prompt_block(memories)
            plan = await self.planner.plan(subject, task, str(tool_args[query_key]), block)
            tool_args = dict(tool_args)
            tool_args[query_key] = plan.query
            plan_note = plan.note
            used_llm = plan.used_llm
            tokens = plan.usage.total_tokens

        # 3) 调工具
        handler = self._tools[tool_name]
        output = await self._invoke(handler, tool_args)

        # 4) 组装结果
        elapsed_ms = (time.perf_counter() - start) * 1000
        return AgentResult(
            feature=feature,
            output=output,
            memories_used=memories_used,
            elapsed_ms=elapsed_ms,
            tokens=tokens,
            plan_note=plan_note,
            used_llm=used_llm,
            trace_id=trace_id,
        )

    @staticmethod
    async def _invoke(handler: Callable, tool_args: dict):
        result = handler(tool_args)
        if inspect.isawaitable(result):
            return await result
        return result

    async def record_feedback(
        self,
        feedback: str,
        user_id: str,
        task_context: str = "",
        trace_id: str = "",
    ) -> list[str]:
        trace_id = trace_id or self._new_trace_id()  # 透传/新建，供日志串联（本层暂无日志出口）

        # 幂等：按 user_id + 反馈内容 hash 去重，防手快多点 / 网络重试重复入库
        feedback_hash = hashlib.sha1(f"{user_id}\x00{feedback}".encode("utf-8")).hexdigest()
        existing = self.store.get_feedback_entry_ids(feedback_hash)
        if existing is not None:
            return existing

        subject = task_context.split(":", 1)[0].strip() if task_context else "通用"
        entries = await self.extractor.extract(
            feedback, user_id=user_id, subject=subject, source=feedback, task_context=task_context
        )
        new_ids = []
        for e in entries:
            eid = self.store.add(e)
            new_ids.append(eid)
            # 冲突处理：同类矛盾旧记忆降权
            self.store.resolve_conflicts(user_id, e.type, e.subject, exclude_entry_id=eid)
        self.store.set_feedback_entry_ids(feedback_hash, new_ids)
        return new_ids
