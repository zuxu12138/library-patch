#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 冷备脚本(无对象存储时的 Litestream 退路)。

把 seats.db / memory.db 用 sqlite3 在线备份 API 复制到带时间戳的文件。
崩溃点可恢复靠 WAL;这里的冷备防"误删/损坏"这种不可再生灾难。

用法:
    python ops/backup.py              # 备份两个库到 backups/
    python ops/backup.py --keep 20    # 每个库只保留最近 20 份
"""
import shutil
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"
CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

DATABASES = [
    ROOT / "collector" / "data" / "seats.db",
    ROOT / "agent" / "memory.db",
]


def backup_one(db_path: Path) -> Path | None:
    if not db_path.exists():
        print(f"[skip] {db_path} 不存在")
        return None
    stamp = datetime.now(CN_TZ).strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"{db_path.stem}-{stamp}.db"
    # sqlite 在线备份 API: 源库被写时也能备出一致快照
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()
    size_kb = dest.stat().st_size // 1024
    print(f"[ok] {db_path.name} -> {dest.name} ({size_kb} KB)")
    return dest


def prune(keep: int) -> None:
    for db in DATABASES:
        backups = sorted(BACKUP_DIR.glob(f"{db.stem}-*.db"))
        for old in backups[:-keep]:
            old.unlink()
            print(f"[prune] 删除旧备份 {old.name}")


def main() -> None:
    keep = 20
    if "--keep" in sys.argv:
        keep = int(sys.argv[sys.argv.index("--keep") + 1])
    BACKUP_DIR.mkdir(exist_ok=True)
    for db in DATABASES:
        backup_one(db)
    prune(keep)


if __name__ == "__main__":
    main()
