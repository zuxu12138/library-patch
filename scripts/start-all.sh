#!/usr/bin/env bash
# library-patch 一键启动 (Git Bash / Linux / macOS)
# 四层: Java service :8080 -> agent :8000 -> web :5173, 外加采集器 loop
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Windows 本机 JDK21 路径; Linux/macOS 改成自己的
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-21}"
export PATH="$JAVA_HOME/bin:$PATH"

PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python3"

echo "== Java service (:8080) =="
(cd service && mvn spring-boot:run -s settings-aliyun.xml -gs settings-aliyun.xml) &
echo "== agent (:8000) =="
("$PY" -m uvicorn agent.main:app --host 127.0.0.1 --port 8000) &
echo "== 座位采集器 (loop 300s) =="
(cd collector && "$PY" seat_collector.py loop 300) &
echo "== web (:5173) =="
(cd web && npm run dev) &

echo ""
echo "全部已拉起。入口: http://localhost:5173"
echo "健康检查: curl http://127.0.0.1:8000/health"
echo "Ctrl-C 停止全部"
wait
