"""LLMClient：兼容 OpenAI 协议的 LLM 调用 + token 计量（04 赛道成本指标）。"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class Usage:
    """一次 LLM 调用的 token 计量。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResult:
    """complete() 的返回：文本 + 用量。"""
    text: str
    usage: Usage


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None
        self.last_usage = Usage()  # 最近一次调用的用量，供 planner 取 token 成本

    @property
    def available(self) -> bool:
        """判断 key 是否可用（有 key + 有 model）。不做网络探测。"""
        return bool(self.api_key) and bool(self.model)

    def _get_client(self):
        if self._client is None:
            # 惰性导入：未装 openai 时 import 本模块也不崩，available 自然为 False
            from openai import AsyncOpenAI

            kwargs = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def complete(self, messages: list[dict], **kw) -> LLMResult:
        if not self.available:
            raise RuntimeError("LLM 未配置（缺少 api_key / model）")
        client = self._get_client()
        resp = await client.chat.completions.create(model=self.model, messages=messages, **kw)
        text = (resp.choices[0].message.content or "") if resp.choices else ""

        usage = Usage()
        u = getattr(resp, "usage", None)
        if u is not None:
            usage = Usage(
                prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(u, "completion_tokens", 0) or 0,
                total_tokens=getattr(u, "total_tokens", 0) or 0,
            )
        self.last_usage = usage
        return LLMResult(text=text, usage=usage)

    async def complete_json(self, messages: list[dict], **kw) -> dict:
        """JSON mode：要求模型只输出 JSON，解析成 dict 返回（解析失败抛异常由调用方处理）。"""
        kw.setdefault("response_format", {"type": "json_object"})
        result = await self.complete(messages, **kw)
        return json.loads(result.text)
