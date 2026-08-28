import importlib

import agent.config as config


def test_defaults_when_env_unset(monkeypatch):
    for key in [
        "SERVICE_BASE_URL", "LLM_BASE_URL", "LLM_API_KEY",
        "LLM_MODEL", "INTERNAL_TOKEN", "SEATS_DB_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)
    importlib.reload(config)
    assert config.SERVICE_BASE_URL == "http://127.0.0.1:8080"
    assert config.LLM_API_KEY == ""
    assert config.LLM_MODEL == "gpt-4o-mini"
    assert config.SEATS_DB_PATH == "collector/data/seats.db"


def test_env_override(monkeypatch):
    monkeypatch.setenv("SERVICE_BASE_URL", "http://example.com")
    importlib.reload(config)
    assert config.SERVICE_BASE_URL == "http://example.com"
    monkeypatch.delenv("SERVICE_BASE_URL", raising=False)
    importlib.reload(config)
