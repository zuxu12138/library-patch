from agent.envelope import AgentError, envelope


def test_envelope_success_shape():
    result = envelope(0, "ok", {"a": 1})
    assert result == {"code": 0, "msg": "ok", "data": {"a": 1}}


def test_envelope_error_shape_has_null_data():
    result = envelope(60001, "LLM 不可用")
    assert result == {"code": 60001, "msg": "LLM 不可用", "data": None}


def test_agent_error_carries_code_and_msg():
    err = AgentError(60002, "记忆库异常")
    assert err.code == 60002
    assert err.msg == "记忆库异常"
