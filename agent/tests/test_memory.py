"""B 模块 · 记忆内核单元测试。

覆盖：
- models: MemoryType / MemoryEntry 默认值 / dedup_key
- store: 存取 / 幂等 / 多用户隔离 / 通配可见 / 类型过滤 / FTS5 全文检索 / 时间衰减 / 冲突降权 / 删除
- retriever: 置信度过滤 / top_k / 提示词块渲染
"""
import pytest

from agent.memory.models import MemoryEntry, MemoryType, dedup_key
from agent.memory.retriever import MemoryRetriever
from agent.memory.store import MemoryStore, time_decay

DAY = 86400.0
HALF_LIFE_DAYS = 30.0


@pytest.fixture
def store():
    s = MemoryStore(":memory:")
    yield s
    s.close()


def make_entry(user_id="u1", type_="preference", subject="找书", content="喜欢靠窗", **kw):
    defaults = dict(user_id=user_id, type=type_, subject=subject, content=content)
    defaults.update(kw)
    return MemoryEntry(**defaults)


# ---------- models ----------


def test_memory_type_values():
    assert MemoryType.PREFERENCE.value == "preference"
    assert MemoryType.RULE.value == "rule"
    assert MemoryType.EPISODE.value == "episode"


def test_entry_defaults():
    e = MemoryEntry(user_id="u1", type="preference", subject="找书", content="喜欢靠窗")
    assert e.applies_to == "*"
    assert e.confidence == 0.8
    assert e.source == ""
    assert e.entry_id == ""
    assert e.created_at == 0.0


def test_dedup_key_stable_and_distinct():
    a = dedup_key("u1", "喜欢靠窗")
    b = dedup_key("u1", "喜欢靠窗")
    c = dedup_key("u1", "喜欢靠门")
    d = dedup_key("u2", "喜欢靠窗")
    assert a == b
    assert a != c
    assert a != d


# ---------- store: 存取 / 幂等 ----------


def test_add_fills_metadata(store):
    e = make_entry()
    eid = store.add(e)
    assert eid
    assert e.entry_id == eid
    assert e.dedup_hash == dedup_key(e.user_id, e.content)
    assert e.created_at > 0
    assert e.updated_at > 0


def test_add_is_idempotent(store):
    e1 = make_entry(content="喜欢靠窗")
    e2 = make_entry(content="喜欢靠窗")
    id1 = store.add(e1)
    id2 = store.add(e2)
    assert id1 == id2
    assert len(store.query("u1")) == 1


def test_get_by_id(store):
    eid = store.add(make_entry(content="x"))
    got = store.get(eid)
    assert got is not None
    assert got.content == "x"


# ---------- store: 隔离 / 通配 / 过滤 ----------


def test_user_isolation(store):
    store.add(make_entry(user_id="u1", content="A 的记忆"))
    store.add(make_entry(user_id="u2", content="B 的记忆"))
    got = store.query("u1")
    assert [e.content for e in got] == ["A 的记忆"]


def test_applies_to_wildcard(store):
    store.add(make_entry(content="通用记忆", applies_to="*"))
    store.add(make_entry(content="座位专属", applies_to="seat_predict"))
    got = store.query("u1", applies_to="findbook")
    contents = [e.content for e in got]
    assert "通用记忆" in contents
    assert "座位专属" not in contents


def test_type_filter(store):
    store.add(make_entry(content="偏好A", type_="preference"))
    store.add(make_entry(content="规则B", type_="rule"))
    got = store.query("u1", type="rule")
    assert [e.content for e in got] == ["规则B"]


# ---------- store: 全文检索 (FTS5 / LIKE 兜底) ----------


def test_text_search_short_like(store):
    store.add(make_entry(content="喜欢靠窗的座位"))
    store.add(make_entry(content="喜欢安静的角落"))
    got = store.query("u1", query_text="靠窗")
    assert [e.content for e in got] == ["喜欢靠窗的座位"]


def test_text_search_fts(store):
    store.add(make_entry(content="只要近五年的书"))
    store.add(make_entry(content="喜欢文学作品"))
    got = store.query("u1", query_text="近五年")
    assert [e.content for e in got] == ["只要近五年的书"]


# ---------- store: 时间衰减 ----------


def test_time_decay_basics():
    now = 1_000_000.0
    assert time_decay(now, now) == pytest.approx(1.0)
    assert time_decay(now - HALF_LIFE_DAYS * DAY, now) == pytest.approx(0.5)
    assert time_decay(now - 2 * HALF_LIFE_DAYS * DAY, now) == pytest.approx(0.25)


def test_decay_sorts_newer_first(store):
    now = 1_700_000_000.0  # 真实量级的 epoch（约 2023 年），保证 "30 天前" 仍为正
    store.add(make_entry(content="旧的", created_at=now - 30 * DAY))
    store.add(make_entry(content="新的", created_at=now))
    got = store.query("u1", now=now)
    assert [e.content for e in got] == ["新的", "旧的"]


# ---------- store: 冲突降权 ----------


def test_resolve_conflicts_downweights_older(store):
    a = make_entry(content="喜欢靠窗", confidence=0.9)
    b = make_entry(content="喜欢靠门", confidence=0.8)
    id_a = store.add(a)
    id_b = store.add(b)
    n = store.resolve_conflicts("u1", "preference", "找书", exclude_entry_id=id_b)
    assert n == 1
    assert store.get(id_a).confidence == pytest.approx(0.45)
    assert store.get(id_b).confidence == pytest.approx(0.8)


# ---------- store: 删除 ----------


def test_delete(store):
    eid = store.add(make_entry(content="待删"))
    assert store.delete(eid) is True
    assert store.query("u1") == []
    assert store.delete(eid) is False


def test_delete_all(store):
    store.add(make_entry(user_id="u1", content="a"))
    store.add(make_entry(user_id="u2", content="b"))
    n = store.delete_all("u1")
    assert n == 1
    assert store.query("u1") == []
    assert len(store.query("u2")) == 1


# ---------- retriever ----------


def test_retriever_confidence_filter(store):
    store.add(make_entry(content="高置信", confidence=0.9))
    store.add(make_entry(content="低置信", confidence=0.3))
    r = MemoryRetriever(store)
    got = r.retrieve("u1", min_confidence=0.5)
    assert [e.content for e in got] == ["高置信"]


def test_retriever_top_k(store):
    for i in range(5):
        store.add(make_entry(content=f"记忆{i}", confidence=0.5 + i * 0.1))
    r = MemoryRetriever(store)
    got = r.retrieve("u1", top_k=2)
    assert len(got) == 2


def test_to_prompt_block(store):
    store.add(make_entry(content="喜欢靠窗", confidence=0.9))
    r = MemoryRetriever(store)
    entries = r.retrieve("u1")
    block = r.to_prompt_block(entries)
    assert "喜欢靠窗" in block
    assert "0.90" in block
    assert "找书" in block
