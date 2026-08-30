#!/usr/bin/env bash
# library-patch 一键启动 (Git Bash / Linux / macOS)
# 四层: Java service :8080 -> agent :8000 -> web :5173, 外加采集器 loop
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Ctrl-C / 异常退出时清掉全部后台进程, 不留孤儿占端口
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

# Windows 本机 JDK21 路径; Linux/macOS 改成自己的
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-21}"
export PATH="$JAVA_HOME/bin:$PATH"

PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

# Windows 系统代理(Clash 等)会被 httpx 读取导致本机调用 502, 强制绕过
export NO_PROXY="127.0.0.1,localhost,[::1]${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

# 端口预检: 已被占用时直接报告, 不再打"全部已拉起"的假消息
PORT_BUSY=0
for port in 8080 8000 5173; do
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$port" 2>/dev/null; then
    echo "[warn] 端口 $port 已被占用, 对应服务可能启动失败" >&2
    PORT_BUSY=1
  fi
done

echo "== Java service (:8080) =="
(cd service && mvn spring-boot:run -s settings-aliyun.xml -gs settings-aliyun.xml) &
echo "== agent (:8000) =="
("$PY" -m uvicorn agent.main:app --host 127.0.0.1 --port 8000) &
echo "== 座位采集器 (loop 300s) =="
(cd collector && "$PY" seat_collector.py loop 300) &
echo "== web (:5173) =="
(cd web && npm run dev) &

echo ""
if [ "$PORT_BUSY" = "1" ]; then
  echo "注意: 有端口被占用, 请检查上面的 [warn] 并处理旧进程"
else
  echo "全部已拉起。入口: http://localhost:5173"
fi
echo "健康检查: curl http://127.0.0.1:8000/health"
echo "Ctrl-C 停止全部"
wait
