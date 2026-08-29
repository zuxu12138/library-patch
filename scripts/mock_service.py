#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""演示兜底 mock 服务(纯标准库)。

OPAC/VPN 现场不通时, 用它顶替 Java 数据层, agent 无感知:
    SERVICE_BASE_URL=http://127.0.0.1:18080 python -m uvicorn agent.main:app

用法:
    python scripts/mock_service.py            # 监听 18080
数据来自 docs/fixtures/(录制的真实响应, 演示前可重录更新)。
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

FIXTURES = Path(__file__).resolve().parent.parent / "docs" / "fixtures"
PORT = 18080


def load(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/books/search":
            # 演示兜底: 任何查询都返回录制的真实响应
            self._send(load("opac-search-deep-learning.json"))
        elif url.path == "/api/seats/now":
            self._send(load("seats-now.json"))
        elif url.path == "/api/health":
            self._send({"code": 0, "msg": "ok", "data": {"status": "ok", "mode": "mock"}})
        else:
            self._send({"code": 40404, "msg": f"mock 未收录 {url.path}", "data": None})

    def log_message(self, fmt, *args):  # 静音访问日志
        pass


if __name__ == "__main__":
    print(f"mock 数据层已启动: http://127.0.0.1:{PORT} (fixtures: {FIXTURES})")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
