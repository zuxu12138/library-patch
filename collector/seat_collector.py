#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大工图书馆座位占用采集器 (角色 A)
- 数据源: 360banke/晓图 座位系统 (公网可达, GBK 编码)
- 采集粒度: 区域级 (GetSeatCount) + 单座级 (GetSeatList)
- 存储: SQLite 时间序列 (WAL), 供 P2 座位预测使用
- 纯标准库, 无需 pip

关键设计 (蓝图横切关注点):
  - 建库设 WAL: 采集器写 + 预测读同库不锁
  - 抓取失败 与 "真没数据" 分开存: 网络抖动不能被模型当成"没人"
  - 时区写死 Asia/Shanghai: 不随机器时区漂移
  - 强制 GBK 解码: 不信响应头 charset

用法:
    python3 seat_collector.py once       # 采一次 (调试)
    python3 seat_collector.py loop        # 循环 (默认 600s)
    python3 seat_collector.py loop 300    # 自定义间隔秒数
"""
import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://www.360banke.com/xiaotu/"
LIBID = "dlut"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DB_PATH = Path(__file__).parent / "data" / "seats.db"
CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")  # 时区写死, 不随机器漂移
DEFAULT_INTERVAL = 600

# ===== 限流器(演示期省资源; 要全量采集时改这两个常量或删掉窗口判断即可) =====
COLLECT_OPEN_HOURS = (7, 23)   # 只在开馆时段采集(Asia/Shanghai), 闭馆数据对预测没价值
SEAT_EVERY_N_TICKS = 3         # 单座级每 N 个 tick 才采一次(一次 15 层请求,区域级每次都采)
# ===========================================================================

# 抓取结果状态 (失败 vs 没数据 必须分开)
FETCH_OK = "ok"
FETCH_FAIL = "fail"      # 网络/解析失败 —— 不代表没人, 预测时须剔除
FETCH_EMPTY = "empty"    # 抓到了但确实无数据

# 直连 opener(空 ProxyHandler = 不走任何代理)
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 直连能力探测缓存: 直连失败后 _DIRECT_BROKEN_UNTIL 之前不再每个请求先白等 15s 超时
_DIRECT_BROKEN_UNTIL = 0.0
_DIRECT_REPROBE_S = 300  # 5 分钟后重新探测直连是否恢复


def http_get(url, timeout=15):
    """GET 请求。返回 (status, text)：
       status ∈ {FETCH_OK, FETCH_FAIL}。FETCH_FAIL 时 text 为 None。
       强制 GBK 解码，不信响应头 charset。
       Windows 系统代理(Clash 等)会被 urllib 自动读取并可能拦断座位接口
       (SSL EOF)，因此直连优先；直连失败后缓存 5 分钟走系统代理，
       避免每个请求都先白等一次直连超时。"""
    global _DIRECT_BROKEN_UNTIL
    req = urllib.request.Request(url, headers={"User-Agent": UA})

    direct_usable = time.time() >= _DIRECT_BROKEN_UNTIL
    if direct_usable:
        try:
            with _DIRECT_OPENER.open(req, timeout=timeout) as resp:
                raw = resp.read()
            return FETCH_OK, raw.decode("gbk", errors="replace")
        except (urllib.error.URLError, OSError):
            _DIRECT_BROKEN_UNTIL = time.time() + _DIRECT_REPROBE_S
            print(f"[warn] direct GET failed {url}, 系统代理兜底(直连冷却 {_DIRECT_REPROBE_S}s)",
                  file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return FETCH_OK, raw.decode("gbk", errors="replace")
    except (urllib.error.URLError, OSError) as e:
        print(f"[warn] GET failed {url}: {e}", file=sys.stderr)
        return FETCH_FAIL, None


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # WAL: 采集器写 + 预测读同库不锁 (持久设置, 设一次即生效)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS area_snapshot (
            ts          TEXT NOT NULL,   -- ISO8601 Asia/Shanghai
            epoch       INTEGER NOT NULL,
            weekday     INTEGER NOT NULL,-- 0=周一 .. 6=周日
            hhmm        TEXT NOT NULL,
            libcode     TEXT,
            mapid       TEXT,
            area_name   TEXT,
            total       INTEGER,
            free        INTEGER,
            occupied    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_area_time ON area_snapshot(weekday, hhmm);
        CREATE INDEX IF NOT EXISTS idx_area_map  ON area_snapshot(mapid);

        CREATE TABLE IF NOT EXISTS seat_snapshot (
            ts TEXT, epoch INTEGER, weekday INTEGER, hhmm TEXT,
            mapid TEXT, seatid TEXT, seatnum TEXT, seattype TEXT, isbusy INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_seat_map ON seat_snapshot(mapid, seatid);

        -- 抓取审计表: 每次采集的状态, 让预测能剔除 FETCH_FAIL 的时刻
        CREATE TABLE IF NOT EXISTS fetch_log (
            ts TEXT NOT NULL, epoch INTEGER NOT NULL,
            scope TEXT NOT NULL,   -- 'area' / 'seat'
            status TEXT NOT NULL,  -- ok / fail / empty
            detail TEXT
        );
        """
    )
    conn.commit()
    return conn



def parse_free_total(name):
    """从区域名 '301阅览室 143/143' 解析 (free, total)；解析不到返回 (None, None)"""
    if not name or "/" not in name:
        return None, None
    tail = name.strip().split()[-1]
    if "/" not in tail:
        return None, None
    try:
        free_s, total_s = tail.split("/", 1)
        return int(free_s), int(total_s)
    except ValueError:
        return None, None


def log_fetch(conn, now, scope, status, detail=""):
    """记录一次抓取状态。失败/空/成功分开存，预测时可据此剔除 FETCH_FAIL 时刻。
    不单独 commit——由调用方在 tick 结束时统一 commit, 减少 fsync 次数。"""
    conn.execute(
        "INSERT INTO fetch_log VALUES (?,?,?,?,?)",
        (now["ts"], now["epoch"], scope, status, detail),
    )


def collect_areas(conn, now):
    """采集区域级占用（一次请求覆盖全部楼层）。失败/空写 fetch_log，不污染 area_snapshot。"""
    status, txt = http_get(f"{BASE}Seatresv/GetSeatCount.asp?libid={LIBID}")
    if status == FETCH_FAIL:
        log_fetch(conn, now, "area", FETCH_FAIL, "http failed")
        return 0
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        # 解析失败 = 抓取失败，绝非"没数据"
        log_fetch(conn, now, "area", FETCH_FAIL, "not json")
        return 0

    areas = data.get("maparea", [])
    if not areas:
        log_fetch(conn, now, "area", FETCH_EMPTY, "no maparea")  # 抓到了但真没数据
        return 0

    # maplist 键统一用 mapid(与 id 同值, 已对照真实接口确认), 键转 str 防类型漂移
    libmap = {str(m.get("mapid")): m.get("libcode") for m in data.get("maplist", [])}
    rows = []
    for a in areas:
        mapid = str(a.get("mapid"))
        name = a.get("name", "")
        free, total = parse_free_total(name)
        if total is None:
            total = a.get("ct")
        occupied = (total - free) if (total is not None and free is not None) else None
        rows.append((
            now["ts"], now["epoch"], now["weekday"], now["hhmm"],
            libmap.get(mapid),
            mapid, name, total, free, occupied,
        ))
    conn.executemany("INSERT INTO area_snapshot VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    log_fetch(conn, now, "area", FETCH_OK, f"{len(rows)} areas")
    conn.commit()
    return len(rows)


def collect_seats(conn, now, mapids):
    """采集单座级占用。每层抓取失败写 fetch_log，不静默跳过；整 tick 一次 commit。"""
    total_rows = 0
    for mapid in mapids:
        status, txt = http_get(f"{BASE}Seatresv/GetSeatList.asp?libid={LIBID}&mapid={mapid}")
        if status == FETCH_FAIL:
            log_fetch(conn, now, "seat", FETCH_FAIL, f"mapid={mapid} http failed")
            continue
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            log_fetch(conn, now, "seat", FETCH_FAIL, f"mapid={mapid} not json")
            continue
        seats = data.get("seats", [])
        if not seats:
            log_fetch(conn, now, "seat", FETCH_EMPTY, f"mapid={mapid} no seats")
            continue
        rows = []
        for s in seats:
            # isbusy 真实值是字符串 "true"/"false", 兼容 "1"/1 防接口字段漂移
            busy = 1 if str(s.get("isbusy")).lower() in ("true", "1") else 0
            rows.append((
                now["ts"], now["epoch"], now["weekday"], now["hhmm"],
                str(mapid), s.get("seatid"), s.get("seatnum"),
                s.get("seattype"), busy,
            ))
        conn.executemany("INSERT INTO seat_snapshot VALUES (?,?,?,?,?,?,?,?,?)", rows)
        total_rows += len(rows)
        time.sleep(0.5)  # 对第三方接口温和一点
    conn.commit()  # 整 tick 一次 commit: 15 层楼从 ~30 次 fsync 降为 1 次
    return total_rows


def list_mapids():
    """从区域接口拿全部楼层 mapid，用于单座采集。
    键名与 collect_areas 统一用 mapid(真实接口 maplist 里 id 与 mapid 同值)。"""
    status, txt = http_get(f"{BASE}Seatresv/GetSeatCount.asp?libid={LIBID}")
    if status == FETCH_FAIL:
        return []
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        return []
    return sorted({str(m.get("mapid")) for m in data.get("maplist", []) if m.get("mapid")})


def now_fields():
    dt = datetime.now(CN_TZ)
    return {
        "ts": dt.isoformat(timespec="seconds"),
        "epoch": int(dt.timestamp()),
        "weekday": dt.weekday(),
        "hhmm": dt.strftime("%H:%M"),
    }


def collect_once(conn, with_seats=True, tick=0, respect_limits=False):
    now = now_fields()
    if respect_limits:
        hour = int(now["hhmm"][:2])
        if not (COLLECT_OPEN_HOURS[0] <= hour < COLLECT_OPEN_HOURS[1]):
            print(f"[{now['ts']}] 闭馆时段({COLLECT_OPEN_HOURS[0]}-{COLLECT_OPEN_HOURS[1]}点外), 跳过")
            return 0, 0
        if tick % SEAT_EVERY_N_TICKS != 0:
            with_seats = False
    n_area = collect_areas(conn, now)
    mapids = list_mapids() if with_seats else []
    if with_seats and n_area > 0 and not mapids:
        # 区域接口成功但拿不到楼层列表: 单座采集会静默为 0, 必须留下痕迹
        log_fetch(conn, now, "seat", FETCH_FAIL, "no mapids from area api")
    n_seat = collect_seats(conn, now, mapids) if mapids else 0
    conn.commit()
    print(f"[{now['ts']}] 区域={n_area} 单座={n_seat}")
    return n_area, n_seat


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    conn = init_db()
    if mode == "once":
        collect_once(conn, with_seats=True)  # 手动调试不受限流器约束
    elif mode == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_INTERVAL
        print(f"采集器启动, 间隔 {interval}s, 写入 {DB_PATH}")
        print(f"限流器: 开馆时段 {COLLECT_OPEN_HOURS[0]}-{COLLECT_OPEN_HOURS[1]}点, 单座每 {SEAT_EVERY_N_TICKS} tick")
        tick = 0
        while True:
            try:
                collect_once(conn, with_seats=True, tick=tick, respect_limits=True)
            except Exception as e:  # noqa: BLE001  循环里任何异常都不中断采集
                print(f"[error] 采集异常: {e}", file=sys.stderr)
            tick += 1
            time.sleep(interval)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
