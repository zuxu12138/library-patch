"""MemoryStore：SQLite + FTS5 的记忆存取。

- 建表: memory(含 dedup_hash 唯一索引) + memory_fts(FTS5 trigram) + feedback_dedup
- add: 按 dedup_hash 幂等（重复内容返回已存在的 entry_id）
- query: FTS5 全文检索(短词 LIKE 兜底) + user_id 隔离 + applies_to 通配 + 时间衰减排序
- resolve_conflicts: 同类矛盾旧记忆降权
- delete / delete_all
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Optional

from agent.memory.models import MemoryEntry, dedup_key

DEFAULT_HALF_LIFE_DAYS = 30.0
DAY = 86400.0


def time_decay(created_at: float, now: float, half_life_days: float = DEFAULT_HALF_LIFE_DAYS) -> float:
    """时间衰减因子 0~1：新记忆接近 1，旧的按半衰期指数衰减。

    "上周喜欢靠窗" 不能永远压过 "昨天喜欢靠门"。
    """
    if half_life_days <= 0:
        return 1.0
    age = max(0.0, now - created_at)
    return 0.5 ** (age / (half_life_days * DAY))


class MemoryStore:
    def __init__(self, db_path: str, half_life_days: float = DEFAULT_HALF_LIFE_DAYS):
        self.half_life_days = half_life_days
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")  # :memory: 下是无害 no-op
        self._has_fts = self._init_schema()

    # ---------- 建表 ----------

    def _init_schema(self) -> bool:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory (
                entry_id   TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                type       TEXT NOT NULL,
                subject    TEXT NOT NULL,
                content    TEXT NOT NULL,
                applies_to TEXT NOT NULL DEFAULT '*',
                confidence REAL NOT NULL DEFAULT 0.8,
                source     TEXT NOT NULL DEFAULT '',
                dedup_hash TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memory_user ON memory(user_id);
            CREATE TABLE IF NOT EXISTS feedback_dedup (
                feedback_hash TEXT PRIMARY KEY,
                entry_ids     TEXT NOT NULL
            );
            """
        )
        has_fts = False
        try:
            # trigram 对中文子串检索友好，3 字及以上可命中
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
                "entry_id UNINDEXED, subject, content, tokenize='trigram')"
            )
            has_fts = True
        except sqlite3.OperationalError:
            # 极少数环境没编译 FTS5 —— 回退 LIKE，功能不丢
            has_fts = False
        self._conn.commit()
        return has_fts

    # ---------- 写 ----------

    def add(self, entry: MemoryEntry) -> str:
        """写入一条记忆，按 dedup_hash 幂等；返回 entry_id（已存在则返回旧 id）。"""
        now = time.time()
        if not entry.entry_id:
            entry.entry_id = uuid.uuid4().hex
        if not entry.dedup_hash:
            entry.dedup_hash = dedup_key(entry.user_id, entry.content)
        if entry.created_at <= 0:
            entry.created_at = now
        if entry.updated_at <= 0:
            entry.updated_at = entry.created_at

        try:
            self._conn.execute(
                "INSERT INTO memory (entry_id, user_id, type, subject, content, applies_to,"
                " confidence, source, dedup_hash, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (entry.entry_id, entry.user_id, entry.type, entry.subject, entry.content,
                 entry.applies_to, entry.confidence, entry.source, entry.dedup_hash,
                 entry.created_at, entry.updated_at),
            )
            self._insert_fts(entry)
            self._conn.commit()
            return entry.entry_id
        except sqlite3.IntegrityError:
            # dedup_hash 唯一索引冲突 → 已存在，返回旧 id（幂等）
            self._conn.rollback()
            row = self._conn.execute(
                "SELECT entry_id FROM memory WHERE dedup_hash = ?", (entry.dedup_hash,)
            ).fetchone()
            entry.entry_id = row["entry_id"]
            return entry.entry_id

    def _insert_fts(self, entry: MemoryEntry) -> None:
        if self._has_fts:
            self._conn.execute(
                "INSERT INTO memory_fts (entry_id, subject, content) VALUES (?,?,?)",
                (entry.entry_id, entry.subject, entry.content),
            )

    # ---------- 读 ----------

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        row = self._conn.execute(
            "SELECT * FROM memory WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def query(
        self,
        user_id: str,
        query_text: Optional[str] = None,
        applies_to: Optional[str] = None,
        type: Optional[str] = None,
        subject: Optional[str] = None,
        limit: Optional[int] = None,
        now: Optional[float] = None,
    ) -> list[MemoryEntry]:
        """检索记忆：user_id 隔离 + 文本检索 + 范围/类型/主题过滤 + 时间衰减排序。"""
        if now is None:
            now = time.time()

        where = ["user_id = ?"]
        params: list = [user_id]
        if type is not None:
            where.append("type = ?")
            params.append(type)
        if subject is not None:
            where.append("subject = ?")
            params.append(subject)
        if applies_to is not None:
            # 通配可见：entry.applies_to == "*" 对任意范围可见
            where.append("(applies_to = ? OR applies_to = '*')")
            params.append(applies_to)

        sql = "SELECT * FROM memory"
        if query_text and query_text.strip():
            ids = self._text_search(query_text.strip())
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            where.append(f"entry_id IN ({placeholders})")
            params.extend(ids)

        sql += " WHERE " + " AND ".join(where)
        rows = self._conn.execute(sql, params).fetchall()
        entries = [self._row_to_entry(r) for r in rows]
        entries.sort(
            key=lambda e: e.confidence * time_decay(e.created_at, now, self.half_life_days),
            reverse=True,
        )
        if limit is not None:
            entries = entries[:limit]
        return entries

    def _text_search(self, text: str) -> list[str]:
        """文本检索：FTS5 trigram(≥3 字) 优先，短词或 FTS 不可用时 LIKE 兜底。"""
        if self._has_fts and len(text) >= 3:
            q = '"' + text.replace('"', "") + '"'
            try:
                rows = self._conn.execute(
                    "SELECT entry_id FROM memory_fts WHERE memory_fts MATCH ?", (q,)
                ).fetchall()
                return [r["entry_id"] for r in rows]
            except sqlite3.OperationalError:
                pass  # 落到 LIKE 兜底
        like = f"%{text}%"
        rows = self._conn.execute(
            "SELECT entry_id FROM memory WHERE content LIKE ? OR subject LIKE ?", (like, like)
        ).fetchall()
        return [r["entry_id"] for r in rows]

    # ---------- 冲突处理 ----------

    def resolve_conflicts(
        self,
        user_id: str,
        type: str,
        subject: str,
        exclude_entry_id: Optional[str] = None,
        factor: float = 0.5,
    ) -> int:
        """同类矛盾旧记忆降权：同一 (user_id, type, subject) 下，除 exclude 外全部乘以 factor。"""
        sql = (
            "UPDATE memory SET confidence = confidence * ?, updated_at = ?"
            " WHERE user_id = ? AND type = ? AND subject = ?"
        )
        params: list = [factor, time.time(), user_id, type, subject]
        if exclude_entry_id is not None:
            sql += " AND entry_id != ?"
            params.append(exclude_entry_id)
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur.rowcount

    # ---------- 删 ----------

    def delete(self, entry_id: str) -> bool:
        if self._has_fts:
            self._conn.execute("DELETE FROM memory_fts WHERE entry_id = ?", (entry_id,))
        cur = self._conn.execute("DELETE FROM memory WHERE entry_id = ?", (entry_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def delete_all(self, user_id: Optional[str] = None) -> int:
        if user_id is None:
            if self._has_fts:
                self._conn.execute("DELETE FROM memory_fts")
            cur = self._conn.execute("DELETE FROM memory")
        else:
            rows = self._conn.execute(
                "SELECT entry_id FROM memory WHERE user_id = ?", (user_id,)
            ).fetchall()
            if self._has_fts:
                for r in rows:
                    self._conn.execute("DELETE FROM memory_fts WHERE entry_id = ?", (r["entry_id"],))
            cur = self._conn.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
        self._conn.commit()
        return cur.rowcount

    # ---------- 反馈级幂等 ----------

    def get_feedback_entry_ids(self, feedback_hash: str) -> Optional[list[str]]:
        row = self._conn.execute(
            "SELECT entry_ids FROM feedback_dedup WHERE feedback_hash = ?", (feedback_hash,)
        ).fetchone()
        return json.loads(row["entry_ids"]) if row else None

    def set_feedback_entry_ids(self, feedback_hash: str, entry_ids: list[str]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO feedback_dedup (feedback_hash, entry_ids) VALUES (?,?)",
            (feedback_hash, json.dumps(entry_ids)),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            user_id=row["user_id"],
            type=row["type"],
            subject=row["subject"],
            content=row["content"],
            applies_to=row["applies_to"],
            confidence=row["confidence"],
            source=row["source"],
            dedup_hash=row["dedup_hash"],
            entry_id=row["entry_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
