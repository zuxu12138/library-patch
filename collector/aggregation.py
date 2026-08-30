#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""座位数据聚合与归档(Phase 2)。

- 把 area_snapshot 聚合为 area_hourly(weekday, hour, 区域平均占用),长期保留;
- 90 天前的 area_snapshot / seat_snapshot 原始行删除(原始数据 TTL);
- fetch_log 同步清理。

预测可直接读 area_hourly(更快、数据量小),也可继续读 area_snapshot。

用法:
    python collector/aggregation.py            # 聚合 + 清理(默认 90 天 TTL)
    python collector/aggregation.py --ttl 60   # 自定义原始数据保留天数
"""
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "seats.db"
DEFAULT_TTL_DAYS = 90
DAY = 86400


def main() -> None:
    ttl_days = DEFAULT_TTL_DAYS
    if "--ttl" in sys.argv:
        ttl_days = int(sys.argv[sys.argv.index("--ttl") + 1])
    cutoff = int(time.time()) - ttl_days * DAY

    if not DB_PATH.exists():
        # sqlite3.connect 会静默新建空库再报 no such table, 掩盖路径配错——先检查
        print(f"[aggregation] 数据库不存在: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout=5000")

    # 1) 聚合: 区域 × weekday × 小时 的平均占用。
    #    增量累计 + 水位线: 只聚合上次水位之后的新原始行, 加权平均合并进历史——
    #    整体重算会被 raw TTL 冲刷掉 90 天前的历史, 违背"长期保留"的设计承诺。
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS area_hourly (
            weekday     INTEGER NOT NULL,
            hour        INTEGER NOT NULL,
            libcode     TEXT,
            mapid       TEXT,
            area_name   TEXT,
            samples     INTEGER NOT NULL,
            avg_occupied REAL,
            avg_total    REAL,
            updated_epoch INTEGER NOT NULL,
            PRIMARY KEY (weekday, hour, mapid, area_name)
        )
        """
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS agg_state (name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
    )
    watermark = conn.execute(
        "SELECT value FROM agg_state WHERE name = 'area_last_epoch'"
    ).fetchone()
    watermark = watermark[0] if watermark else 0
    now_epoch = int(time.time())
    # 水位线取本批行的最大 epoch 而非 now(): 聚合进行中采集器并发写入的行
    # (epoch <= now) 不会被错误地永久跳过
    batch_max = conn.execute(
        "SELECT MAX(epoch) FROM area_snapshot WHERE epoch > ?", (watermark,)
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO area_hourly (weekday, hour, libcode, mapid, area_name,
                                 samples, avg_occupied, avg_total, updated_epoch)
        SELECT weekday,
               CAST(substr(hhmm, 1, 2) AS INTEGER) AS hour,
               MAX(libcode), mapid, area_name,
               COUNT(*), AVG(occupied), AVG(total), ?
        FROM area_snapshot
        WHERE epoch > ?
        GROUP BY weekday, hour, mapid, area_name
        ON CONFLICT(weekday, hour, mapid, area_name) DO UPDATE SET
            -- 加权平均合并新批次, 历史不被 raw TTL 冲刷
            samples = area_hourly.samples + excluded.samples,
            avg_occupied = (area_hourly.avg_occupied * area_hourly.samples
                            + excluded.avg_occupied * excluded.samples)
                           / (area_hourly.samples + excluded.samples),
            avg_total = (area_hourly.avg_total * area_hourly.samples
                         + excluded.avg_total * excluded.samples)
                        / (area_hourly.samples + excluded.samples),
            updated_epoch = excluded.updated_epoch
        """,
        (now_epoch, watermark),
    )
    if batch_max is not None:
        conn.execute(
            "INSERT INTO agg_state VALUES ('area_last_epoch', ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
            (batch_max,),
        )

    # 2) 清理过期原始数据与日志
    cur1 = conn.execute("DELETE FROM area_snapshot WHERE epoch < ?", (cutoff,))
    cur2 = conn.execute("DELETE FROM seat_snapshot WHERE epoch < ?", (cutoff,))
    cur3 = conn.execute("DELETE FROM fetch_log WHERE epoch < ?", (cutoff,))
    # WAL 长期只增不减, 顺手收掉; 有其他读者(agent/采集器)持库时 checkpoint 会被拒,
    # 属可跳过的维护动作, 不能让聚合结果陪葬
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.OperationalError as e:
        print(f"[aggregation] wal_checkpoint 跳过: {e}", file=sys.stderr)
    conn.commit()

    hourly_count = conn.execute("SELECT COUNT(*) FROM area_hourly").fetchone()[0]
    print(
        f"[aggregation] area_hourly={hourly_count} 行; "
        f"清理 raw: area={cur1.rowcount} seat={cur2.rowcount} fetch_log={cur3.rowcount}"
    )
    conn.close()


if __name__ == "__main__":
    main()
