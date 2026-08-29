import sqlite3

import pytest

from agent.features.seat_predict.service import SeatPredictService
from agent.service_client import ServiceUnavailable
from agent.tests.fakes import FakeAgentLoop


def _make_seats_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE area_snapshot (weekday INTEGER, hhmm TEXT, area_name TEXT, occupied INTEGER, total INTEGER)"
    )
    rows = [
        (1, "14:05", "301阅览室", 140, 175),
        (1, "14:35", "301阅览室", 120, 175),
        (1, "14:05", "201文艺期刊阅览室", 30, 175),
        (1, "14:35", "201文艺期刊阅览室", 50, 175),
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

    async def seats_now(self, trace_id):
        if self.raise_error is not None:
            raise self.raise_error
        return {"count": 1, "areas": []}


@pytest.mark.asyncio
async def test_predict_sorts_areas_by_ascending_occupancy_rate(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

    result = await service.predict(weekday=1, hour=14, user_id="u1", trace_id="abc123")

    ranking = result.output["ranking"]
    assert ranking[0]["area_name"] == "201文艺期刊阅览室"
    assert ranking[0]["avg_occupancy_rate"] == pytest.approx(40 / 175, abs=1e-4)
    assert ranking[1]["area_name"] == "301阅览室"
    assert ranking[1]["avg_occupancy_rate"] == pytest.approx(130 / 175, abs=1e-4)


@pytest.mark.asyncio
async def test_predict_ignores_realtime_correction_when_service_unavailable(tmp_path):
    db_path = str(tmp_path / "seats.db")
    _make_seats_db(db_path)
    loop = FakeAgentLoop()
    stub = _StubServiceClient()
    stub.raise_error = ServiceUnavailable("boom")
    service = SeatPredictService(loop, stub, seats_db_path=db_path)

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
