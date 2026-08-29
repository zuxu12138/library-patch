# 座位采集器运维

`seat_collector.py` 使用纯 Python 标准库，不需要安装第三方包。

## 手动运行

```bash
python3 seat_collector.py once
python3 seat_collector.py loop 600
```

数据写入 `data/seats.db`。采集器建库时启用 SQLite WAL；网络失败和确实无数据分别记录在 `fetch_log`，不会把失败误当成空座位。

## macOS launchd 常驻

1. 打开 `com.dlut.seatcollector.plist`，将 `__PYTHON_BIN__` 和 `__PROJECT_DIR__` 替换为绝对路径。
2. 安装并启动：

```bash
cp com.dlut.seatcollector.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.dlut.seatcollector.plist
```

查看状态：

```bash
launchctl print "gui/$(id -u)/com.dlut.seatcollector"
```

停止并卸载：

```bash
launchctl bootout "gui/$(id -u)/com.dlut.seatcollector"
```

日志默认写入 `/tmp/library-patch-seat-collector.log` 和 `/tmp/library-patch-seat-collector-error.log`。

## Litestream 备份

`litestream.yml` 是持续备份模板。设置数据库和副本地址后启动：

```bash
export SEATS_DB_PATH="$PWD/data/seats.db"
export SEATS_REPLICA_URL="s3://your-bucket/library-patch/seats"
litestream replicate -config litestream.yml
```

访问密钥、region、endpoint 等按对象存储供应商要求配置。备份目标不要放入 git。
