"""Planner：用记忆精炼查询。无 key / 无记忆时原样透传，异常降级不打断主流程。"""
from __future__ import annotations

from dataclasses import dataclass

from agent.core.llm import Usage


@dataclass
class PlanResult:
    query: str      # 精炼后（或原样）的检索词
    note: str       # 给用户的一句话说明，如 "已按你的偏好只找近五年"
    used_llm: bool  # 本次是否真调用了 LLM
    usage: Usage    # token 计量


class Planner:
    SYSTEM = (
        "你是查询精炼器。根据用户的记忆偏好，把当前检索词精炼成更精准的检索词，"
        '并生成一句给用户看的简短说明 note。只输出 JSON：{"query": "...", "note": "..."}。'
        "不要臆造记忆里没有的约束；记忆不相关就原样返回检索词。"
    )

    def __init__(self, llm):
        self.llm = llm

    async def plan(self, subject: str, task: str, query: str, memories_block: str = "") -> PlanResult:
        # 无 key 或无记忆 → 原样透传，不打断主流程
        if not self.llm.available or not memories_block:
            return PlanResult(query=query, note="", used_llm=False, usage=Usage())

        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": (
                f"主题: {subject}\n任务: {task}\n当前检索词: {query}\n\n{memories_block}"
            )},
        ]
        try:
            data = await self.llm.complete_json(messages)
            new_query = str(data.get("query") or "").strip() or query
            note = str(data.get("note") or "").strip()
            return PlanResult(query=new_query, note=note, used_llm=True, usage=self.llm.last_usage)
        except Exception:
            # 异常降级：精炼失败就当没记忆，原样透传
            return PlanResult(query=query, note="", used_llm=False, usage=Usage())
