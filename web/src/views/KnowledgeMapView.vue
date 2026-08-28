<script setup lang="ts">
import { echarts, type ECharts } from "../charts";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { buildGraph, summarizePaper, type CitationGraph, type PaperSummary } from "../api/knowledge";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const paperId = ref("");
const activePaperId = ref(""); // 当前图的中心(下钻后变)
const loading = ref(false);
const errorMessage = ref("");
const graph = ref<CitationGraph | null>(null);
const summary = ref<PaperSummary | null>(null);
const chartContainer = ref<HTMLDivElement | null>(null);
const feedbackOpen = ref(false);
let chart: ECharts | null = null;

// 移动端退化为列表
const isMobile = ref(window.matchMedia("(max-width: 639px)").matches);
const mq = window.matchMedia("(max-width: 639px)");
const onMq = (e: MediaQueryListEvent) => (isMobile.value = e.matches);
onMounted(() => mq.addEventListener("change", onMq));
onBeforeUnmount(() => mq.removeEventListener("change", onMq));

// 摘要逐段浮现
const abstractParas = computed(() =>
  (summary.value?.abstract ?? "").split(/\n+/).filter((p) => p.trim())
);

async function loadGraph(targetId?: string) {
  const id = (targetId ?? paperId.value).trim();
  if (!id) return;
  loading.value = true;
  errorMessage.value = "";
  summary.value = null;
  graph.value = null;
  try {
    const g = await buildGraph(id);
    if (g.error) {
      errorMessage.value = g.error;
      return;
    }
    graph.value = g;
    activePaperId.value = id;
    await nextTick();
    renderChart(g);
    // 摘要独立加载, 失败不影响图
    try {
      const s = await summarizePaper(id);
      if (!s.error) summary.value = s;
    } catch {
      /* 摘要降级缺失不阻塞 */
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

function renderChart(g: CitationGraph) {
  if (isMobile.value || !chartContainer.value || !g.nodes.length) return;
  if (!chart) chart = echarts.init(chartContainer.value);
  chart.setOption({
    animationDuration: 400,
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true, // 滚轮缩放 + 拖拽平移
        force: { repulsion: 220, edgeLength: 90 },
        // hover 时无关节点降至低透明度, 仅高亮关联路径
        emphasis: { focus: "adjacency", lineStyle: { color: "#0f5c5c", width: 2 } },
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          fontFamily: "Inter, sans-serif",
          color: "#4a4a46",
          overflow: "truncate",
          width: 130,
        },
        data: g.nodes.map((n, i) => ({
          id: n.paperId,
          name: n.title ?? (i === 0 ? "当前论文" : n.paperId),
          symbolSize: i === 0 ? 20 : 12,
          itemStyle:
            i === 0
              ? {
                  color: "#0f5c5c",
                  // 中心光晕用 box-shadow, 不用 filter: blur(防性能问题)
                  shadowBlur: 14,
                  shadowColor: "rgba(15, 92, 92, 0.45)",
                }
              : { color: "#1c1c1a" },
        })),
        links: g.edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: { color: "#e6e6df", width: 1.2 },
        })),
      },
    ],
  });
  // 点击节点下钻为新中心
  chart.off("click");
  chart.on("click", (params: unknown) => {
    const p = params as { dataType?: string; data?: { id?: string } | null };
    if (p.dataType === "node" && p.data?.id && p.data.id !== activePaperId.value) {
      paperId.value = p.data.id;
      loadGraph(p.data.id);
    }
  });
}

// 移动端/无图时的列表退化
function drill(id: string) {
  paperId.value = id;
  loadGraph(id);
}

async function submitFeedback(text: string) {
  const { http, unwrap } = await import("../api/client");
  return await unwrap<{ memory_ids: string[]; llm_available: boolean }>(
    http.post("/memory/feedback", { feedback: text, task_context: `知识地图:${activePaperId.value}` })
  );
}
</script>

<template>
  <section class="knowledge">
    <header class="page-head">
      <h1 class="page-title">知识地图</h1>
      <p class="page-sub">从一篇论文出发，沿引用脉络走下去</p>
    </header>

    <form class="searchbar" role="search" @submit.prevent="loadGraph()">
      <input
        v-model="paperId"
        type="search"
        placeholder="输入论文 paperId，如 arXiv:1706.03762"
        aria-label="论文 ID"
      />
      <button type="submit">展开</button>
    </form>

    <LoadingState v-if="loading" :rows="4" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <template v-else-if="graph">
      <p class="graph-meta">
        <span class="mono">{{ activePaperId }}</span> · {{ graph.nodes.length - 1 }} 篇引用
        <span class="drill-hint">点击节点可下钻</span>
      </p>

      <!-- 桌面: 力导向星图 -->
      <div
        v-if="!isMobile"
        ref="chartContainer"
        class="chart"
        aria-label="论文引用关系图"
      ></div>

      <!-- 移动端: 一维关联列表 -->
      <ul v-else class="node-list">
        <li v-for="n in graph.nodes.slice(1)" :key="n.paperId">
          <button type="button" class="node-link" @click="drill(n.paperId)">
            <span class="node-title">{{ n.title ?? n.paperId }}</span>
            <span v-if="n.year" class="node-year mono">{{ n.year }}</span>
          </button>
        </li>
      </ul>

      <!-- 摘要: 逐段浮现 + 作者胶片条 + PDF 印章 -->
      <article v-if="summary" class="summary">
        <div class="summary-head">
          <div class="summary-title-wrap">
            <h2 class="summary-title">{{ summary.title ?? "摘要" }}</h2>
            <p v-if="summary.year" class="summary-year mono">{{ summary.year }}</p>
          </div>
          <a
            v-if="summary.openAccessPdf?.url"
            :href="summary.openAccessPdf.url"
            target="_blank"
            rel="noopener"
            class="pdf-seal"
          >
            <span class="seal-text">PDF</span>
            <span v-if="summary.openAccessPdf.license" class="seal-license">{{ summary.openAccessPdf.license }}</span>
          </a>
        </div>

        <div v-if="summary.authors?.length" class="authors-strip" aria-label="作者列表">
          <span v-for="a in summary.authors" :key="a.name" class="author-chip">{{ a.name }}</span>
        </div>

        <p
          v-for="(p, i) in abstractParas"
          :key="i"
          class="abstract-para rise-in"
          :style="{ animationDelay: `${i * 200}ms` }"
        >
          {{ p }}
        </p>
        <p v-if="!abstractParas.length" class="abstract-para dim">该论文暂无摘要文本。</p>
      </article>
    </template>

    <p v-else class="empty-invite">输入 paperId 开始探索 —— 图谱会像星图一样展开</p>

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
  margin-bottom: 2rem;
}

.page-title {
  font-family: var(--font-serif);
  font-size: 2.25rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 0;
}

.page-sub {
  margin: 0.5rem 0 0;
  color: var(--color-ink-soft);
  font-size: 15px;
}

.mono {
  font-family: var(--font-mono);
}

.searchbar {
  display: flex;
  align-items: stretch;
  max-width: 640px;
  margin: 0 auto 2rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  overflow: hidden;
}

.searchbar:focus-within {
  border-color: var(--color-teal);
}

.searchbar input {
  flex: 1;
  min-width: 0;
  min-height: 52px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  padding: 0 1rem;
  font-family: var(--font-mono);
}

.searchbar input::placeholder {
  color: var(--color-ink-muted);
  font-family: var(--font-sans);
}

.searchbar button {
  flex-shrink: 0;
  padding: 0 1.75rem;
  border: none;
  background: var(--color-teal);
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: background 0.15s ease;
}

.searchbar button:hover {
  background: var(--color-teal-deep);
}

.graph-meta {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  font-size: 12.5px;
  color: var(--color-ink-muted);
  border-bottom: 1px solid var(--color-line);
  padding-bottom: 0.6rem;
  margin-bottom: 1rem;
  overflow: hidden;
}

.drill-hint {
  margin-left: auto;
  font-size: 11.5px;
}

.chart {
  width: 100%;
  height: 440px;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
}

/* 移动端列表退化 */
.node-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.node-list li {
  border-bottom: 1px solid var(--color-line);
}

.node-link {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  min-height: 44px;
  padding: 0.7rem 0.25rem;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.node-title {
  font-size: 14.5px;
  color: var(--color-ink);
  line-height: 1.5;
}

.node-link:hover .node-title {
  color: var(--color-teal);
}

.node-year {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

/* 摘要卡片 */
.summary {
  position: relative;
  margin-top: 1.5rem;
  padding: 1.5rem 1.75rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
}

.summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.summary-title {
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 600;
  line-height: 1.45;
  margin: 0;
}

.summary-year {
  margin: 0.35rem 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

/* 赭红印章式 PDF 角标 */
.pdf-seal {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  border: 1.5px solid var(--color-seal);
  border-radius: 50%;
  color: var(--color-seal);
  text-decoration: none;
  transform: rotate(-8deg);
  transition: transform 0.2s ease;
}

.pdf-seal:hover {
  transform: rotate(-4deg) scale(1.05);
}

.seal-text {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.seal-license {
  font-size: 8.5px;
  letter-spacing: 0.04em;
}

/* 作者胶片条 */
.authors-strip {
  display: flex;
  gap: 0.5rem;
  margin: 1rem 0;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding-bottom: 0.3rem;
}

.author-chip {
  scroll-snap-align: start;
  flex-shrink: 0;
  font-size: 12.5px;
  color: var(--color-ink-soft);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 0.25rem 0.7rem;
  white-space: nowrap;
  background: var(--color-paper);
}

.abstract-para {
  margin: 0 0 0.9rem;
  font-size: 15px;
  line-height: 1.85;
  color: var(--color-ink-soft);
}

.abstract-para.dim {
  color: var(--color-ink-muted);
}

.empty-invite {
  text-align: center;
  color: var(--color-ink-muted);
  margin: 3rem 0 0;
  font-size: 14px;
}

@media (max-width: 640px) {
  .page-title {
    font-size: 1.7rem;
  }
  .summary {
    padding: 1.1rem 1.15rem;
  }
}
</style>
