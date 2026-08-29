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

    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout=5000")

    # 1) 聚合: 区域 × weekday × 小时 的平均占用
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
        """
        INSERT INTO area_hourly (weekday, hour, libcode, mapid, area_name,
                                 samples, avg_occupied, avg_total, updated_epoch)
        SELECT weekday,
               CAST(substr(hhmm, 1, 2) AS INTEGER) AS hour,
               MAX(libcode), mapid, area_name,
               COUNT(*), AVG(occupied), AVG(total), ?
        FROM area_snapshot
        GROUP BY weekday, hour, mapid, area_name
        ON CONFLICT(weekday, hour, mapid, area_name) DO UPDATE SET
            samples = excluded.samples,
            avg_occupied = excluded.avg_occupied,
            avg_total = excluded.avg_total,
            updated_epoch = excluded.updated_epoch
        """,
        (int(time.time()),),
    )

    # 2) 清理过期原始数据与日志
    cur1 = conn.execute("DELETE FROM area_snapshot WHERE epoch < ?", (cutoff,))
    cur2 = conn.execute("DELETE FROM seat_snapshot WHERE epoch < ?", (cutoff,))
    cur3 = conn.execute("DELETE FROM fetch_log WHERE epoch < ?", (cutoff,))
    conn.commit()

    hourly_count = conn.execute("SELECT COUNT(*) FROM area_hourly").fetchone()[0]
    print(
        f"[aggregation] area_hourly={hourly_count} 行; "
        f"清理 raw: area={cur1.rowcount} seat={cur2.rowcount} fetch_log={cur3.rowcount}"
    )
    conn.close()


if __name__ == "__main__":
    main()
