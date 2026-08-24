"""MemoryRetriever：按 user_id 隔离检索记忆，渲染成紧凑提示词块。"""
from __future__ import annotations

from typing import Optional

from agent.memory.store import MemoryStore


class MemoryRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def retrieve(
        self,
        user_id: str,
        subject: Optional[str] = None,
        applies_to: Optional[str] = None,
        query_text: Optional[str] = None,
        type: Optional[str] = None,
        top_k: int = 5,
        min_confidence: float = 0.0,
    ) -> list:
        """检索 top_k 条记忆：user_id 隔离 + 置信度阈值 + 衰减后综合得分排序(store 已排)。"""
        entries = self.store.query(
            user_id,
            query_text=query_text,
            applies_to=applies_to,
            type=type,
            subject=subject,
        )
        entries = [e for e in entries if e.confidence >= min_confidence]
        return entries[:top_k]

    def to_prompt_block(self, entries) -> str:
        """把命中的记忆渲染成一段紧凑提示词，供 planner 注入。"""
        if not entries:
            return ""
        lines = ["【用户记忆】"]
        for e in entries:
            lines.append(f"- [{e.type}/{e.subject}] {e.content} (置信度 {e.confidence:.2f})")
        return "\n".join(lines)
