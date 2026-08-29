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
        """检索 top_k 条记忆：user_id 隔离 + 置信度阈值 + 衰减后综合得分排序。

        query_text 用于相关性**提权**而非过滤：偏好类记忆（如"只看近五年"）
        与查询词（如"深度学习"）往往无字面重合，纯 FTS 过滤会把它们错杀。
        做法：FTS 命中的排前面，其余按置信度×衰减排后，共同进入 top_k。
        """
        matched: list = []
        if query_text:
            matched = self.store.query(
                user_id, query_text=query_text, applies_to=applies_to, type=type, subject=subject
            )
        scoped = self.store.query(
            user_id, applies_to=applies_to, type=type, subject=subject
        )
        seen: set = set()
        out: list = []
        for e in matched + scoped:  # matched 优先,scoped 补齐
            if e.entry_id in seen:
                continue
            seen.add(e.entry_id)
            if e.confidence >= min_confidence:
                out.append(e)
        return out[:top_k]

    def to_prompt_block(self, entries) -> str:
        """把命中的记忆渲染成一段紧凑提示词，供 planner 注入。"""
        if not entries:
            return ""
        lines = ["【用户记忆】"]
        for e in entries:
            lines.append(f"- [{e.type}/{e.subject}] {e.content} (置信度 {e.confidence:.2f})")
        return "\n".join(lines)
