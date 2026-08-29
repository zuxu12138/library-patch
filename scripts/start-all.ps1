# library-patch 一键启动 (Windows PowerShell)
# 四层: Java service :8080 -> agent :8000 -> web :5173, 外加采集器 loop
# 用法: powershell -File scripts/start-all.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$jdk21 = "C:\Program Files\Java\jdk-21"
$env:JAVA_HOME = $jdk21

Write-Host "== 1/4 Java service (:8080) ==" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root\service'; `$env:JAVA_HOME='$jdk21'; `$env:PATH='$jdk21\bin;' + `$env:PATH; mvn spring-boot:run -s settings-aliyun.xml -gs settings-aliyun.xml"

Write-Host "== 2/4 agent (:8000, venv) ==" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root'; .\.venv\Scripts\python.exe -m uvicorn agent.main:app --host 127.0.0.1 --port 8000"

Write-Host "== 3/4 座位采集器 (loop 300s) ==" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root\collector'; ..\.venv\Scripts\python.exe seat_collector.py loop 300"

Write-Host "== 4/4 web (:5173) ==" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "cd '$root\web'; npm run dev"

Write-Host ""
Write-Host "全部已拉起。入口: http://localhost:5173" -ForegroundColor Green
Write-Host "健康检查: curl http://127.0.0.1:8000/health"
