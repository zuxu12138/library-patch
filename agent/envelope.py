"""统一响应信封 {code, msg, data}（docs/接口契约.md 全局约定）。"""
from __future__ import annotations

from typing import Any


class AgentError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


def envelope(code: int, msg: str, data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}
