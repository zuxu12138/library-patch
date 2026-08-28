<script setup lang="ts">
import * as echarts from "echarts";
import { nextTick, ref } from "vue";
import { buildGraph, summarizePaper } from "../api/knowledge";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const paperId = ref("");
const loading = ref(false);
const errorMessage = ref("");
const summary = ref<Record<string, unknown> | null>(null);
const chartContainer = ref<HTMLDivElement | null>(null);
const hasGraph = ref(false);
const feedbackOpen = ref(false);
let chart: echarts.ECharts | null = null;

async function loadGraph() {
  if (!paperId.value.trim()) return;
  loading.value = true;
  errorMessage.value = "";
  summary.value = null;
  hasGraph.value = false;
  try {
    const graph = await buildGraph(paperId.value);
    hasGraph.value = graph.nodes.length > 0;
    await nextTick();
    if (chartContainer.value && hasGraph.value) {
      if (!chart) chart = echarts.init(chartContainer.value);
      chart.setOption({
        animationDuration: 600,
        series: [
          {
            type: "graph",
            layout: "force",
            roam: true,
            label: {
              show: true,
              position: "right",
              fontSize: 12,
              color: "#1a1a2e",
              overflow: "truncate",
              width: 130,
            },
            data: graph.nodes.map((n, i) => ({
              id: n.paperId,
              name: n.title ?? n.paperId,
              symbolSize: i === 0 ? 22 : 14,
              itemStyle:
                i === 0
                  ? { color: "#c8102e", borderColor: "#9c0d24", borderWidth: 1 }
                  : { color: "#003da5", borderColor: "#002c78", borderWidth: 1 },
            })),
            links: graph.edges.map((e) => ({
              source: e.source,
              target: e.target,
              lineStyle: { color: "#b9c8e8", width: 1.4, opacity: 0.75 },
            })),
          },
        ],
      });
    }
    summary.value = await summarizePaper(paperId.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  const { http, unwrap } = await import("../api/client");
  await unwrap(
    http.post("/memory/feedback", { feedback: text, task_context: `知识地图:${paperId.value}` })
  );
  feedbackOpen.value = false;
}
</script>

<template>
  <section class="knowledge-map">
    <header class="page-head">
      <h1 class="page-title">知识地图</h1>
      <p class="page-sub">输入论文 ID，展开它的引用脉络</p>
    </header>

    <form @submit.prevent="loadGraph" class="searchbar" role="search">
      <span class="search-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" />
          <line x1="20" y1="20" x2="16.5" y2="16.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </span>
      <input
        v-model="paperId"
        type="search"
        placeholder="输入论文 paperId，如 arXiv:1706.03762"
        aria-label="论文 ID"
      />
      <button type="submit">展开</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <template v-else>
      <div
        v-show="hasGraph"
        ref="chartContainer"
        class="chart"
        aria-label="论文引用关系图"
      ></div>

      <div v-if="summary" class="summary">
        <h2>摘要</h2>
        <pre>{{ summary }}</pre>
      </div>
    </template>

    <FeedbackFab
      :open="feedbackOpen"
      :on-submit="submitFeedback"
      @toggle="feedbackOpen = !feedbackOpen"
    />
  </section>
</template>

<style scoped>
.page-head {
  text-align: center;
  margin-bottom: 1.75rem;
}

.page-title {
  font-size: var(--fs-page);
}

.page-sub {
  margin: 0.4rem 0 0;
  color: var(--ink-soft);
}

.searchbar {
  position: relative;
  display: flex;
  align-items: center;
  width: 600px;
  max-width: 100%;
  height: 52px;
  margin: 0 auto 2rem;
  background: var(--card);
  border: 1.5px solid var(--line);
  border-radius: 26px;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.searchbar:focus-within {
  border-color: var(--dut-blue);
  box-shadow: 0 0 0 4px rgba(0, 61, 165, 0.12);
}

.search-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 46px;
  color: var(--ink-muted);
}

.searchbar input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--fs-body);
  padding: 0 0.25rem;
}

.searchbar input::placeholder {
  color: var(--ink-muted);
}

.searchbar button {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 1.5rem;
  border: none;
  background: var(--dut-blue);
  color: #fff;
  font-size: var(--fs-body);
  font-weight: 600;
  transition: background 0.2s ease;
}

.searchbar button:hover {
  background: var(--dut-blue-bright);
}

.chart {
  width: 100%;
  height: 420px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

.summary {
  margin-top: 1.25rem;
  padding: 1.1rem 1.25rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

.summary h2 {
  font-size: var(--fs-module);
  margin-bottom: 0.5rem;
}

.summary pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-soft);
}
</style>
