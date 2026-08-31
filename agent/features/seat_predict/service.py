"""P2 座位预测(笨基线)。同 weekday+同时段历史平均占用率升序排序推荐，
稳、可解释，先上线顶着，日后可当模型对照组。只读连接设 busy_timeout，
不建表不设WAL(建库/WAL 是采集器/A 的职责)。

⚠️ 表结构以 A 的采集器为准: area_snapshot(weekday, hhmm, area_name, occupied, total),
小时从 hhmm 前两位提取(如 "11:31" → 11)。

开闭馆: 大工图书馆 07:00–22:00。闭馆时段实时接口返回的是"全空"假象
(座位系统闭馆后清空占用), 直接展示会误导; 闭馆时跳过实时融合,
只回历史规律并显式标记 is_open=false, 由前端呈现闭馆态。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from agent.service_client import ServiceUnavailable

# 开馆时段 [OPEN_HOUR, CLOSE_HOUR), 与采集器 COLLECT_OPEN_HOURS 保持一致
OPEN_HOUR = 7
CLOSE_HOUR = 22
# 时区写死 Asia/Shanghai(无夏令时), 不随机器时区漂移
CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _is_open_hour(hour: int) -> bool:
    return OPEN_HOUR <= hour < CLOSE_HOUR


def _now_cn() -> datetime:
    return datetime.now(CN_TZ)


class SeatPredictService:
    def __init__(self, agent_loop, service_client, seats_db_path: str, now_fn=_now_cn):
        self._agent_loop = agent_loop
        self._service_client = service_client
        self._db_path = seats_db_path
        self._now_fn = now_fn  # 可注入, 测试用固定时刻
        self._agent_loop.register_tool("predict_seats", self._predict_tool)

    def _read_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _predict_tool(self, tool_args: dict) -> dict:
        # AgentLoop 契约: handler 接收 tool_args(dict), 见 agent/core/agent_loop.py
        weekday, hour, trace_id = tool_args["weekday"], tool_args["hour"], tool_args["trace_id"]
        # API 契约 weekday 1=周一..7=周日; 采集库存 dt.weekday() 0=周一..6=周日 —— 必须换算
        db_weekday = weekday - 1
        try:
            conn = self._read_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT area_name, AVG(occupied) AS avg_occupied, AVG(total) AS avg_total,
                           COUNT(*) AS samples
                    FROM area_snapshot
                    WHERE weekday = ? AND substr(hhmm, 1, 2) = ?
                    GROUP BY area_name
                    """,
                    (db_weekday, f"{hour:02d}"),
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            # DB 缺失/锁定/表不存在: 按采集器故障降级, 不裸抛 sqlite 原文成 500
            raise ServiceUnavailable(f"seats history db unavailable: {type(exc).__name__}") from exc

        now = self._now_fn()
        is_open = _is_open_hour(hour)
        # 实时占用只对「当前时刻」有意义: 未来/历史时段没有实时可言;
        # 闭馆时段座位系统返回"全空"假象, 同样不可信
        is_current = db_weekday == now.weekday() and hour == now.hour

        # 实时目录(map_id/lib_code/区域名)任何时段都需要——下钻平面图与分馆筛选靠它;
        # 但空闲数字与占用融合只在 开馆 && 当前时刻 使用
        realtime: dict[str, dict] = {}
        realtime_ok = False
        try:
            now_data = await self._service_client.seats_now(trace_id)
            for area in (now_data or {}).get("areas", []):
                realtime[area.get("areaName", "")] = area
            realtime_ok = True
        except Exception:
            # 实时接口任何故障都降级为纯历史预测, 不影响主流程
            realtime_ok = False

        show_realtime = realtime_ok and is_open and is_current
        fetched_at = now.strftime("%H:%M") if show_realtime else None

        history: dict[str, dict] = {}
        for area_name, avg_occupied, avg_total, samples in rows:
            history[area_name] = {
                "avg_occupancy_rate": (avg_occupied / avg_total) if avg_total else 0.0,
                "samples": samples,
            }

        # 历史不足(采样点 < MIN_SAMPLES)时实时数据权重更高;
        # 完全没有历史就纯按实时空闲排序——否则冷启动阶段推荐全是平手
        MIN_SAMPLES = 4
        names = set(history) | set(realtime)
        ranking = []
        for name in names:
            h = history.get(name)
            rt = realtime.get(name)
            # 实时空闲数只在开馆的当前时刻展示/融合; 其余时段只借目录字段(map_id/lib_code)
            rt_live = rt if show_realtime else None
            score = 0.0
            if h and rt_live and rt_live.get("total"):
                rt_rate = (rt_live["total"] - rt_live.get("free", 0)) / rt_live["total"]
                w = min(1.0, h["samples"] / MIN_SAMPLES)  # 历史权重随采样点数增长
                score = w * h["avg_occupancy_rate"] + (1 - w) * rt_rate
            elif h:
                score = h["avg_occupancy_rate"]
            elif rt_live and rt_live.get("total"):
                score = (rt_live["total"] - rt_live.get("free", 0)) / rt_live["total"]
            ranking.append({
                "area_name": name,
                "avg_occupancy_rate": round(score, 4),
                "samples": h["samples"] if h else 0,
                "free_now": rt_live.get("free") if rt_live else None,
                "total": rt_live.get("total") if rt_live else None,
                # 楼层 id / 馆代码, 供前端下钻座位平面图与分馆筛选
                "map_id": rt.get("mapId") if rt else None,
                "lib_code": rt.get("libCode") if rt else None,
            })
        ranking.sort(key=lambda item: item["avg_occupancy_rate"])

        return {
            "ranking": ranking,
            "realtime_available": show_realtime,
            "is_open": is_open,
            "open_hours": [OPEN_HOUR, CLOSE_HOUR],
            "fetched_at": fetched_at,  # 实时数据拉取时刻(Asia/Shanghai HH:MM); 非当前时段/闭馆/降级时为 None
        }

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

    async def seat_map(self, map_id: str, trace_id: str) -> dict:
        """单座级实时平面图(纯数据透传, 不经记忆闭环)。
        附带 is_open/fetched_at: 闭馆时前端据真数据(全"不可预约")呈现闭馆快照。"""
        data = await self._service_client.seats_map(map_id, trace_id)
        if isinstance(data, dict):
            now = self._now_fn()
            data = {
                **data,
                "is_open": _is_open_hour(now.hour),
                "fetched_at": now.strftime("%H:%M"),
                "open_hours": [OPEN_HOUR, CLOSE_HOUR],
            }
        return data

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"座位纠错:{feedback[:30]}",
            trace_id=trace_id,
        )
