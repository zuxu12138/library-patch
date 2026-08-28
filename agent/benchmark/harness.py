"""04 赛道 FOCUS 指标采集。跑一批找书任务, 聚合 token成本/延迟/记忆命中率。
记忆误用率需人工标注负反馈样本，本轮不做自动化，报告里留字符串占位说明。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(eq=True)
class TaskMetric:
    task_name: str
    elapsed_ms: float
    tokens: int
    memory_hit: bool
    used_llm: bool


class BenchmarkHarness:
    def __init__(self, findbook_service):
        self._findbook = findbook_service
        self._metrics: list[TaskMetric] = []

    async def run_task(self, query: str, user_id: str, trace_id: str) -> TaskMetric:
        result = await self._findbook.find(query, page=1, page_size=10, user_id=user_id, trace_id=trace_id)
        metric = TaskMetric(
            task_name=query,
            elapsed_ms=result.elapsed_ms,
            tokens=result.tokens,
            memory_hit=len(result.memories_used) > 0,
            used_llm=result.used_llm,
        )
        self._metrics.append(metric)
        return metric

    async def run_batch(self, queries: list[str], user_id: str = "benchmark") -> list[TaskMetric]:
        results = []
        for query in queries:
            trace_id = uuid.uuid4().hex[:8]
            results.append(await self.run_task(query, user_id=user_id, trace_id=trace_id))
        return results

    def report(self) -> dict:
        if not self._metrics:
            return {
                "avg_elapsed_ms": 0.0, "total_tokens": 0,
                "memory_hit_rate": 0.0, "memory_misuse_rate": "待人工标注",
            }
        total = len(self._metrics)
        return {
            "avg_elapsed_ms": sum(m.elapsed_ms for m in self._metrics) / total,
            "total_tokens": sum(m.tokens for m in self._metrics),
            "memory_hit_rate": sum(1 for m in self._metrics if m.memory_hit) / total,
            "memory_misuse_rate": "待人工标注",
        }

    def to_markdown(self) -> str:
        report = self.report()
        lines = ["# Benchmark Report", ""]
        for key, value in report.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def save(self, path: str = "agent/benchmark/report.json") -> str:
        """把报告持久化成 JSON(04 赛道指标留档), 返回文件路径。"""
        import json
        import time

        payload = {"generated_epoch": int(time.time()), **self.report()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path
