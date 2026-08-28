import json

from agent.features.knowledge_map.s2_cache import S2Cache


def test_get_returns_none_when_missing(tmp_path):
    cache = S2Cache(path=str(tmp_path / "cache.json"))
    assert cache.get("paper:p1") is None


def test_set_then_get_roundtrips(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = S2Cache(path=str(cache_path))
    cache.set("paper:p1", {"title": "A"})
    assert cache.get("paper:p1") == {"title": "A"}

    reloaded = S2Cache(path=str(cache_path))
    assert reloaded.get("paper:p1") == {"title": "A"}


def test_set_persists_valid_json_file(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = S2Cache(path=str(cache_path))
    cache.set("k", {"v": 1})
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"k": {"v": 1}}
