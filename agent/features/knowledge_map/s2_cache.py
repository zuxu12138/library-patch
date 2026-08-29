"""S2 持久缓存(横切关注点②C的一半)。引用关系稳定，缓存显著降低429。
JSON 文件缓存，纯 key-value，不知道 HTTP 细节。"""
from __future__ import annotations

import json
import os


class S2Cache:
    def __init__(self, path: str = "agent/features/knowledge_map/.s2_cache.json"):
        self._path = path

    def get(self, key: str) -> dict | None:
        data = self._load()
        return data.get(key)

    def set(self, key: str, value: dict) -> None:
        data = self._load()
        data[key] = value
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, encoding="utf-8") as f:
            return json.load(f)
