import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from agent.features.seat_predict.service import SeatPredictService
from agent.service_client import ServiceUnavailable
from agent.tests.fakes import FakeAgentLoop

CN_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
# 2026-08-31 是周一(dt.weekday()==0, 采集库约定); API 契约周一为 weekday=1
MON_1400 = datetime(2026, 8, 31, 14, 0, tzinfo=CN_TZ)
MON_2300 = datetime(2026, 8, 31, 23, 0, tzinfo=CN_TZ)


def _make_seats_db(path: str) -> None:
    """采集库约定: weekday 0=周一..6=周日, hhmm "HH:MM"。"""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE area_snapshot (weekday INTEGER, hhmm TEXT, area_name TEXT, occupied INTEGER, total INTEGER)"
    )
    rows = [
        (0, "14:05", "301阅览室", 140, 175),
        (0, "14:35", "301阅览室", 120, 175),
        (0, "14:05", "201文艺期刊阅览室", 30, 175),
        (0, "14:35", "201文艺期刊阅览室", 50, 175),
        (0, "23:05", "301阅览室", 10, 175),
    ]
    conn.executemany(
        "INSERT INTO area_snapshot (weekday, hhmm, area_name, occupied, total) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


class _StubServiceClient:
    def __init__(self):
        self.raise_error: Exception | None = None
        self.seats_now_calls = 0

    async def seats_now(self, trace_id):
        self.seats_now_calls += 1
        if self.raise_error is not None:
            raise self.raise_error
        return {
            "count": 1,
            "areas": [
                {"areaName": "301阅览室", "free": 40, "total": 175, "mapId": "2498", "libCode": "bochuan"}
            ],
        }


def _make_service(db_path, stub, now):
    return SeatPredictService(FakeAgentLoop(), stub, seats_db_path=db_path, now_fn=lambda: now)


@pytest.mark.asyncio
async def test_predict_sorts_areas_by_ascending_occupancy_rate(tmp_path):
    """API weekday=1(周一) 必须命中采集库 weekday=0; 非当前时段纯按历史排序。"""
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    stub = _StubServiceClient()
    service = _make_service(db_path, stub, MON_2300)  # 查询 14 点 ≠ 当前 23 点

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    ranking = result.output["ranking"]
    assert ranking[0]["area_name"] == "201文艺期刊阅览室"
    assert ranking[0]["avg_occupancy_rate"] == pytest.approx(40 / 175, abs=1e-4)
    assert ranking[1]["area_name"] == "301阅览室"
    assert ranking[1]["avg_occupancy_rate"] == pytest.approx(130 / 175, abs=1e-4)


@pytest.mark.asyncio
async def test_predict_non_current_hour_uses_catalog_but_not_live_counts(tmp_path):
    """未来/历史时段: 实时目录(map_id/lib_code)可用, 但空闲数字不展示、不参与融合。"""
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    stub = _StubServiceClient()
    service = _make_service(db_path, stub, MON_2300)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    assert result.output["is_open"] is True  # 14 点开馆, 但不是当前时刻
    assert result.output["realtime_available"] is False
    assert result.output["fetched_at"] is None
    assert stub.seats_now_calls == 1  # 目录仍拉取, 保留下钻/筛选
    row_301 = next(r for r in result.output["ranking"] if r["area_name"] == "301阅览室")
    assert row_301["free_now"] is None
    assert row_301["map_id"] == "2498"
    # 纯历史: 130/175, 不被实时 40/175 污染
    assert row_301["avg_occupancy_rate"] == pytest.approx(130 / 175, abs=1e-4)


@pytest.mark.asyncio
async def test_predict_closed_hour_marks_closed(tmp_path):
    """闭馆时段(22 点后): 显式标记闭馆, 实时空闲数不展示(座位系统闭馆返回全空假象)。"""
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    stub = _StubServiceClient()
    service = _make_service(db_path, stub, MON_2300)

    result = await service.predict(weekday=1, hour=23, user_id="u1", trace_id="abc123")

    assert result.output["is_open"] is False
    assert result.output["open_hours"] == [7, 22]
    assert result.output["realtime_available"] is False
    assert result.output["fetched_at"] is None
    # 历史规律仍可用, 供开馆后参考
    row_301 = next(r for r in result.output["ranking"] if r["area_name"] == "301阅览室")
    assert row_301["avg_occupancy_rate"] == pytest.approx(10 / 175, abs=1e-4)
    assert row_301["free_now"] is None


@pytest.mark.asyncio
async def test_predict_open_current_hour_fuses_realtime(tmp_path):
    """开馆的当前时刻: 实时空闲展示并参与融合, 带拉取时间戳。"""
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    stub = _StubServiceClient()
    service = _make_service(db_path, stub, MON_1400)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    assert result.output["is_open"] is True
    assert result.output["realtime_available"] is True
    assert result.output["fetched_at"] == "14:00"
    row_301 = next(r for r in result.output["ranking"] if r["area_name"] == "301阅览室")
    assert row_301["free_now"] == 40
    # 融合: samples=2 < MIN_SAMPLES=4 → w=0.5; 0.5*(130/175) + 0.5*(135/175)
    expected = 0.5 * (130 / 175) + 0.5 * (135 / 175)
    assert row_301["avg_occupancy_rate"] == pytest.approx(expected, abs=1e-4)


@pytest.mark.asyncio
async def test_predict_ignores_realtime_correction_when_service_unavailable(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    stub = _StubServiceClient()
    stub.raise_error = ServiceUnavailable("boom")
    service = _make_service(db_path, stub, MON_1400)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    assert len(result.output["ranking"]) == 2
    assert result.output.get("realtime_available") is False


@pytest.mark.asyncio
async def test_feedback_delegates_to_agent_loop_record_feedback(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    loop.next_feedback_ids = ["mem-2"]
    stub = _StubServiceClient()
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

    ids = await service.feedback("这层其实很吵", user_id="u1", trace_id="abc123")

    assert ids == ["mem-2"]
    call = loop.feedback_calls[0]
    assert call["task_context"] == "座位纠错:这层其实很吵"
