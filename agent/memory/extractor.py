"""MemoryExtractor：用 LLM 从一句反馈抽取 0-3 条结构化记忆。

JSON mode + pydantic 校验，校验失败重试一次再丢弃；无 key 返回空；失败不打断。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent.memory.models import MemoryEntry, MemoryType


class ExtractedMemory(BaseModel):
    """LLM 输出的单条记忆结构（pydantic 校验，content 必填非空）。"""
    type: str = "preference"
    subject: str = ""
    content: str = Field(min_length=1)
    applies_to: str = "*"
    confidence: float = 0.8


class ExtractedMemories(BaseModel):
    memories: list[ExtractedMemory] = Field(default_factory=list)
    # 与本次反馈矛盾的已有记忆 entry_id 列表（由 LLM 点名，精准降权用）
    contradicts: list[str] = Field(default_factory=list)


class MemoryExtractor:
    SYSTEM = (
        "你是记忆抽取器。从用户反馈中抽取 0-3 条值得长期记住的结构化记忆。"
        "每条含 type(preference/rule/episode)、subject(主题)、content(正文)、"
        'applies_to(适用功能范围, 默认 "*")、confidence(0~1)。'
        "若提供了已有记忆,判断本次反馈是否与其中某条直接矛盾"
        "(如旧记忆说喜欢靠窗、新反馈说喜欢靠门),把矛盾记忆的 id 放进 contradicts 数组;"
        "不矛盾(靠窗 vs 安静)不要放。"
        '没有可沉淀的就返回 {"memories": [], "contradicts": []}。只输出 JSON。'
    )

    def __init__(self, llm, max_items: int = 3):
        self.llm = llm
        self.max_items = max_items
        self.last_contradicts: list[str] = []  # 最近一次 extract 判定的矛盾记忆 id

    async def extract(self, feedback, user_id, subject="", source="", task_context="", existing=None) -> list[MemoryEntry]:
        self.last_contradicts = []
        if not self.llm.available:
            return []
        existing_block = ""
        if existing:
            lines = [f"- id={e.entry_id} [{e.type}/{e.subject}] {e.content}" for e in existing[:10]]
            existing_block = "已有记忆:\n" + "\n".join(lines) + "\n\n"
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": f"{existing_block}任务上下文: {task_context}\n用户反馈: {feedback}"},
        ]
        for attempt in range(2):  # 校验失败重试一次，再失败就丢弃
            try:
                data = await self.llm.complete_json(messages)
                parsed = ExtractedMemories.model_validate(data)
                valid_ids = {e.entry_id for e in existing} if existing else set()
                self.last_contradicts = [c for c in parsed.contradicts if c in valid_ids]
                return self._to_entries(parsed, user_id, subject, source)
            except Exception:
                if attempt == 1:
                    return []  # 别让解析残渣混进记忆库
        return []

    def _to_entries(self, parsed: ExtractedMemories, user_id, subject, source) -> list[MemoryEntry]:
        valid_types = {t.value for t in MemoryType}
        entries = []
        for item in parsed.memories[: self.max_items]:
            content = item.content.strip()
            if not content:
                continue
            typ = item.type if item.type in valid_types else MemoryType.PREFERENCE.value
            subj = item.subject.strip() or subject or "通用"
            conf = max(0.0, min(1.0, item.confidence))
            entries.append(MemoryEntry(
                user_id=user_id,
                type=typ,
                subject=subj,
                content=content,
                applies_to=item.applies_to or "*",
                confidence=conf,
                source=source,
            ))
        return entries
