"""C 名下的测试替身。用于在 B(AgentLoop)、A(Java) 交付前独立测试 C 的业务逻辑。
严格对齐 docs/接口契约.md 契约②的字段/签名。不导入 agent.core，避免 B 未交付时
测试因 ImportError 失败。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


@dataclass
class FakeAgentResult:
    feature: str
    output: Any
    memories_used: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    tokens: int = 0
    plan_note: str = ""
    used_llm: bool = False
    trace_id: str = ""


class FakeAgentLoop:
    """契约②(AgentLoop.run / record_feedback)的测试替身。"""

    def __init__(self) -> None:
        self.tools: dict[str, Callable] = {}
        self.run_calls: list[dict] = []
        self.feedback_calls: list[dict] = []
        self.next_result: FakeAgentResult | None = None
        self.next_feedback_ids: list[str] = ["fake-memory-id"]

    def register_tool(self, name: str, fn: Callable) -> None:
        self.tools[name] = fn

    async def run(
        self,
        *,
        feature: str,
        subject: str,
        task: str,
        tool_name: str,
        tool_args: dict,
        user_id: str,
        trace_id: str,
        query_key: str | None = None,
    ) -> FakeAgentResult:
        self.run_calls.append(
            dict(
                feature=feature, subject=subject, task=task,
                tool_name=tool_name, tool_args=tool_args,
                user_id=user_id, trace_id=trace_id, query_key=query_key,
            )
        )
        tool_fn = self.tools[tool_name]
        output = await tool_fn(tool_args)  # 与 AgentLoop 契约一致: handler 接收 tool_args(dict)
        if self.next_result is not None:
            result, self.next_result = self.next_result, None
            return result
        return FakeAgentResult(feature=feature, output=output, trace_id=trace_id)

    async def record_feedback(
        self,
        *,
        feedback: str,
        user_id: str,
        task_context: str = "",
        trace_id: str = "",
    ) -> list[str]:
        self.feedback_calls.append(
            dict(feedback=feedback, user_id=user_id, task_context=task_context, trace_id=trace_id)
        )
        return self.next_feedback_ids


def envelope_response(status_code: int, code: int, msg: str, data: Any = None) -> httpx.Response:
    """构造带 {code,msg,data} 信封的 httpx.Response，供 MockTransport handler 使用。"""
    return httpx.Response(status_code, json={"code": code, "msg": msg, "data": data})
