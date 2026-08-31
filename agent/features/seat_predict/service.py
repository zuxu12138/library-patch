"""P2 座位预测(笨基线)。同 weekday+同时段历史平均占用率升序排序推荐，
稳、可解释，先上线顶着，日后可当模型对照组。只读连接设 busy_timeout，
不建表不设WAL(建库/WAL 是采集器/A 的职责)。

⚠️ 表结构以 A 的采集器为准: area_snapshot(weekday, hhmm, area_name, occupied, total),
小时从 hhmm 前两位提取(如 "11:31" → 11)。
"""
from __future__ import annotations

import sqlite3
import time

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

    async def _availability_tool(self, args):
        from datetime import datetime, timezone, timedelta
        mode = args['mode']
        now = datetime.now(timezone(timedelta(hours=8)))
        closed = mode == 'now' and now.hour >= 22
        # API Monday=1; collector Monday=0. Historical dates receive equal weight.
        weekday, hour = args['weekday'] - 1, args['hour']
        conn = self._read_conn()
        conn.row_factory = sqlite3.Row
        try:
            latest = [dict(r) for r in conn.execute(
                'SELECT * FROM area_availability WHERE epoch=(SELECT MAX(epoch) FROM area_availability)')]
            daily = [dict(r) for r in conn.execute('''
                SELECT mapid, substr(ts,1,10) day, AVG(available) available, AVG(total) total
                FROM area_availability WHERE weekday=? AND substr(hhmm,1,2)=?
                AND unknown=0 AND substr(ts,1,10) < ? GROUP BY mapid, substr(ts,1,10)
            ''', (weekday, f'{hour:02d}', now.date().isoformat()))]
        except sqlite3.OperationalError:
            latest, daily = [], []
        finally:
            conn.close()
        by_map = {}
        for item in daily: by_map.setdefault(item['mapid'], []).append(item)
        ranking = []
        for row in latest:
            history = by_map.get(row['mapid'], [])
            days = len(history)
            reliable = days >= 3
            age = max(0, int(now.timestamp()) - row['epoch'])
            fresh = age <= 600 and not closed
            available = row['available'] if fresh and mode == 'now' else None
            estimated = round(sum(h['available'] for h in history) / days) if reliable else None
            rate = 1 - (sum(h['available']/h['total'] for h in history if h['total']) / days) if reliable else None
            ranking.append({
                'area_name': row['area_name'], 'map_id': row['mapid'], 'lib_code': row['libcode'],
                'total': row['total'], 'free_now': available, 'samples': days, 'sample_days': days,
                'avg_occupancy_rate': (1-row['available']/row['total']) if mode=='now' and fresh and row['total'] else rate if mode=='plan' else None,
                'predicted_available': estimated if mode=='plan' else None,
                'occupied_now': row['occupied'] if fresh and mode=='now' else None,
                'unavailable_now': row['unavailable'] if fresh and mode=='now' else None,
                'unknown_now': row['unknown'] if fresh and mode=='now' else None,
                'updated_at': row['ts'], 'age_seconds': age, 'fresh': fresh,
                'recommendable': (available is not None and available > 0) if mode=='now' else (estimated is not None and estimated > 0),
            })
        ranking.sort(key=lambda r: (not r['recommendable'], -(r['free_now'] if mode=='now' and r['free_now'] is not None else r['predicted_available'] or 0), r['area_name']))
        return {'ranking': ranking, 'mode': mode, 'closed': closed,
                'realtime_available': mode=='now' and any(r['fresh'] for r in ranking),
                'message': ('已闭馆：按本项目设置，北京时间 22:00 起暂停当前座位推荐。可切换“计划去”查看历史参考。' if closed else '按最近采集快照推荐，状态不代表实际在馆人数。' if mode=='now' else
                            '只使用所选星期、时段的历史记录；至少 3 个不同日期才给出估计。')}

    async def _predict_tool(self, tool_args: dict) -> dict:
        if tool_args.get("mode") in ("now", "plan"):
            return await self._availability_tool(tool_args)
        # AgentLoop 契约: handler 接收 tool_args(dict), 见 agent/core/agent_loop.py
        weekday, hour, trace_id = tool_args["weekday"], tool_args["hour"], tool_args["trace_id"]
        recent = []
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
                    (weekday, f"{hour:02d}"),
                ).fetchall()
                # Prefer the collector's complete recent floor snapshot; avoid 15 upstream
                # requests on every page load. Old snapshots never masquerade as current.
                try:
                    recent = conn.execute(
                        "SELECT mapid, area_name, libcode, total, free FROM area_snapshot "
                        "WHERE epoch = (SELECT MAX(epoch) FROM area_snapshot) AND epoch >= ?",
                        (int(time.time()) - 600,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    recent = []
            finally:
                conn.close()
        except sqlite3.Error as exc:
            # DB 缺失/锁定/表不存在: 按采集器故障降级, 不裸抛 sqlite 原文成 500
            raise ServiceUnavailable(f"seats history db unavailable: {type(exc).__name__}") from exc

        # 实时占用：拿来修正/兜底,不再只是标个布尔就扔
        realtime: dict[str, dict] = {}
        realtime_available = True
        try:
            if recent:
                now = {"areas": [{"mapId": mid, "areaName": name, "libCode": lib,
                                   "total": total, "free": free}
                                  for mid, name, lib, total, free in recent]}
            else:
                now = await self._service_client.seats_now(trace_id)
            for area in (now or {}).get("areas", []):
                realtime[area.get("areaName", "")] = area
        except Exception:
            # 实时接口任何故障都降级为纯历史预测, 不影响主流程
            realtime_available = False

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
            score = 0.0
            if h and rt and rt.get("total"):
                rt_rate = (rt["total"] - rt.get("free", 0)) / rt["total"]
                w = min(1.0, h["samples"] / MIN_SAMPLES)  # 历史权重随采样点数增长
                score = w * h["avg_occupancy_rate"] + (1 - w) * rt_rate
            elif h:
                score = h["avg_occupancy_rate"]
            elif rt and rt.get("total"):
                score = (rt["total"] - rt.get("free", 0)) / rt["total"]
            ranking.append({
                "area_name": name,
                "avg_occupancy_rate": round(score, 4),
                "samples": h["samples"] if h else 0,
                "free_now": rt.get("free") if rt else None,
                "total": rt.get("total") if rt else None,
                # 楼层 id / 馆代码, 供前端下钻座位平面图与分馆筛选
                "map_id": rt.get("mapId") if rt else None,
                "lib_code": rt.get("libCode") if rt else None,
            })
        ranking.sort(key=lambda item: item["avg_occupancy_rate"])

        return {"ranking": ranking, "realtime_available": realtime_available}

    async def predict(self, weekday: int, hour: int, user_id: str, trace_id: str, mode: str | None = None):
        return await self._agent_loop.run(
            feature="seat_predict",
            subject="座位预测",
            task=f"预测: weekday={weekday} hour={hour}",
            tool_name="predict_seats",
            tool_args={"weekday": weekday, "hour": hour, "trace_id": trace_id, "mode": mode},
            user_id=user_id,
            trace_id=trace_id,
            query_key=None,
        )

    async def seat_map(self, map_id: str, trace_id: str) -> dict:
        """单座级实时平面图(纯数据透传, 不经记忆闭环)。"""
        return await self._service_client.seats_map(map_id, trace_id)

    async def feedback(self, feedback: str, user_id: str, trace_id: str) -> list[str]:
        return await self._agent_loop.record_feedback(
            feedback=feedback,
            user_id=user_id,
            task_context=f"座位纠错:{feedback[:30]}",
            trace_id=trace_id,
        )
