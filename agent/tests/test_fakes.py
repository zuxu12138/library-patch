import httpx
import pytest

from agent.tests.fakes import FakeAgentLoop, envelope_response


@pytest.mark.asyncio
async def test_fake_agent_loop_invokes_registered_tool():
    loop = FakeAgentLoop()

    async def tool(tool_args: dict) -> int:
        return tool_args["x"] * 2

    loop.register_tool("double", tool)

    result = await loop.run(
        feature="findbook", subject="s", task="t",
        tool_name="double", tool_args={"x": 21, "trace_id": "abc123"},
        user_id="u1", trace_id="abc123",
    )

    assert result.output == 42
    assert result.feature == "findbook"
    assert result.trace_id == "abc123"
    assert loop.run_calls[0]["tool_name"] == "double"
    assert loop.run_calls[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_fake_agent_loop_record_feedback_records_call_and_returns_ids():
    loop = FakeAgentLoop()
    loop.next_feedback_ids = ["mem-1"]

    ids = await loop.record_feedback(feedback="喜欢靠窗", user_id="u1", task_context="找书:x", trace_id="abc123")

    assert ids == ["mem-1"]
    assert loop.feedback_calls[0]["feedback"] == "喜欢靠窗"
    assert loop.feedback_calls[0]["task_context"] == "找书:x"


def test_envelope_response_builds_expected_json():
    resp = envelope_response(200, 0, "ok", {"a": 1})
    assert resp.status_code == 200
    assert resp.json() == {"code": 0, "msg": "ok", "data": {"a": 1}}
