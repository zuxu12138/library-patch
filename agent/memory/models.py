"""记忆数据模型。

- MemoryType: preference / rule / episode
- MemoryEntry: 契约 ② 定的字段（C 只读不建）
- dedup_key: 按 user_id + 内容 计算幂等去重键
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    RULE = "rule"
    EPISODE = "episode"


def dedup_key(user_id: str, content: str) -> str:
    """幂等去重键：同一用户 + 同一内容 → 同一键（稳定、跨进程一致）。"""
    raw = f"{user_id}\x00{content}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


@dataclass
class MemoryEntry:
    """一条结构化记忆。字段与接口契约 ② 完全一致，C 只读不建。"""

    user_id: str            # ★ 多用户隔离
    type: str               # preference / rule / episode
    subject: str            # 主题, 如 "找书"
    content: str            # 记忆正文
    applies_to: str = "*"   # 适用功能范围, "*" 通配
    confidence: float = 0.8  # 置信度
    source: str = ""        # 溯源: 由哪条反馈抽取
    dedup_hash: str = ""    # ★ 幂等去重(user_id + 内容 hash)
    entry_id: str = ""      # 唯一 id
    created_at: float = 0.0  # 供时间衰减
    updated_at: float = 0.0
