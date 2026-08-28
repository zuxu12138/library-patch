import pytest

from agent.benchmark.harness import BenchmarkHarness, TaskMetric
from agent.features.findbook.service import FindBookService
from agent.tests.fakes import FakeAgentLoop, FakeAgentResult


class _StubServiceClient:
    async def search_books(self, query, page, page_size, trace_id):
        return {"total": 1, "books": [{"title": query}]}


@pytest.mark.asyncio
async def test_run_task_returns_metric_from_agent_result():
    loop = FakeAgentLoop()
    loop.next_result = FakeAgentResult(
        feature="findbook", output={"books": []}, memories_used=["m1"],
        elapsed_ms=12.5, tokens=42, used_llm=True, trace_id="abc123",
    )
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)

    metric = await harness.run_task("机器学习", user_id="benchmark", trace_id="abc123")

    assert metric == TaskMetric(
        task_name="机器学习", elapsed_ms=12.5, tokens=42, memory_hit=True, used_llm=True,
    )


@pytest.mark.asyncio
async def test_run_batch_collects_one_metric_per_query():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)

    metrics = await harness.run_batch(["机器学习", "数据结构"])

    assert [m.task_name for m in metrics] == ["机器学习", "数据结构"]
    assert len(harness._metrics) == 2


@pytest.mark.asyncio
async def test_report_aggregates_metrics():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)
    harness._metrics = [
        TaskMetric(task_name="a", elapsed_ms=10.0, tokens=5, memory_hit=True, used_llm=True),
        TaskMetric(task_name="b", elapsed_ms=20.0, tokens=15, memory_hit=False, used_llm=True),
    ]

    report = harness.report()

    assert report["avg_elapsed_ms"] == pytest.approx(15.0)
    assert report["total_tokens"] == 20
    assert report["memory_hit_rate"] == pytest.approx(0.5)
    assert report["memory_misuse_rate"] == "待人工标注"


def test_to_markdown_includes_report_fields():
    loop = FakeAgentLoop()
    service = FindBookService(loop, _StubServiceClient())
    harness = BenchmarkHarness(service)
    harness._metrics = [
        TaskMetric(task_name="a", elapsed_ms=10.0, tokens=5, memory_hit=True, used_llm=True),
    ]

    markdown = harness.to_markdown()

    assert "avg_elapsed_ms" in markdown
    assert "memory_hit_rate" in markdown
