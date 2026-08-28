"""P2 座位预测(笨基线)。同 weekday+同时段历史平均占用率升序排序推荐，
稳、可解释，先上线顶着，日后可当模型对照组。只读连接设 busy_timeout，
不建表不设WAL(建库/WAL 是采集器/A 的职责)。

⚠️ 表结构以 A 的采集器为准: area_snapshot(weekday, hhmm, area_name, occupied, total),
小时从 hhmm 前两位提取(如 "11:31" → 11)。
"""
from __future__ import annotations

import sqlite3

from agent.service_client import ServiceUnavailable


class SeatPredictService:
    def __init__(self, agent_loop, service_client, seats_db_path: str):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._db_path = seats_db_path
        self._agent_loop.register_tool("predict_seats", self._predict_tool)

    def _read_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _predict_tool(self, tool_args: dict) -> dict:
        # AgentLoop 契约: handler 接收 tool_args(dict), 见 agent/core/agent_loop.py
        weekday, hour, trace_id = tool_args["weekday"], tool_args["hour"], tool_args["trace_id"]
        conn = self._read_conn()
        try:
            rows = conn.execute(
                """
                SELECT area_name, AVG(occupied) AS avg_occupied, AVG(total) AS avg_total
                FROM area_snapshot
                WHERE weekday = ? AND substr(hhmm, 1, 2) = ?
                GROUP BY area_name
                """,
                (weekday, f"{hour:02d}"),
            ).fetchall()
        finally:
            conn.close()

        ranking = [
            {
                "area_name": area_name,
                "avg_occupancy_rate": (avg_occupied / avg_total) if avg_total else 0.0,
            }
            for area_name, avg_occupied, avg_total in rows
        ]
        ranking.sort(key=lambda item: item["avg_occupancy_rate"])

        realtime_available = True
        try:
            await self._service_client.seats_now(trace_id)
        except ServiceUnavailable:
            realtime_available = False

        return {"ranking": ranking, "realtime_available": realtime_available}

    async def predict(self, weekday: int, hour: int, user_id: str, trace_id: str):
        return await self._agent_loop.run(
            feature="seat_predict",
            subject="座位预测",
            task=f"预测: weekday={weekday} hour={hour}",
            tool_name="predict_seats",
            tool_args={"weekday": weekday, "hour": hour, "trace_id": trace_id},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"座位纠错:{feedback[:30]}",
            trace_id=trace_id,
        )
