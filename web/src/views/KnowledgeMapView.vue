<script setup lang="ts">
import { echarts, type ECharts } from "../charts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  buildGraph,
  searchPapers,
  summarizePaper,
  type CitationGraph,
  type GraphNode,
  type PaperSummary,
} from "../api/knowledge";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";
import SealStamp from "../components/SealStamp.vue";
import { inkDrop } from "../ink/ink";

const paperId = ref("");
const activePaperId = ref(""); // 当前图的中心(下钻后变)
const activeTitle = ref("");   // 中心论文标题(从搜索结果带过来)
const loading = ref(false);
const errorMessage = ref("");
const graph = ref<CitationGraph | null>(null);
const summary = ref<PaperSummary | null>(null);
const chartContainer = ref<HTMLDivElement | null>(null);
const feedbackOpen = ref(false);
let chart: ECharts | null = null;
let chartResizeObserver: ResizeObserver | null = null;
let graphRequest = 0;

function disposeChart() {
  chartResizeObserver?.disconnect();
  chartResizeObserver = null;
  chart?.dispose();
  chart = null;
}

// v-if creates a new container after loading; initialize only once it exists.
watch([chartContainer, graph], ([container, data]) => {
  disposeChart();
  if (!container || !data?.nodes.length) return;
  renderChart(data);
  chartResizeObserver = new ResizeObserver(() => chart?.resize());
  chartResizeObserver.observe(container);
}, { flush: "post" });
onBeforeUnmount(() => { graphRequest++; disposeChart(); });

// 关键词找论文(不知道 paperId 的入口)
const showSearch = ref(false);
const searchQuery = ref("");
const searching = ref(false);
const searchResults = ref<GraphNode[]>([]);
const searchError = ref("");
const searched = ref(false);

async function doSearchPapers() {
  if (!searchQuery.value.trim()) return;
  searching.value = true;
  searchError.value = "";
  searchResults.value = [];
  try {
    const r = await searchPapers(searchQuery.value.trim());
    if (r.error) searchError.value = r.error;
    else {
      searchResults.value = r.papers;
      inkDrop();
    }
  } catch (err) {
    searchError.value = err instanceof Error ? err.message : "检索失败，请稍后再试";
  } finally {
    searching.value = false;
    searched.value = true;
  }
}

function pickPaper(p: GraphNode) {
  paperId.value = p.paperId;
  activeTitle.value = p.title ?? "";
  showSearch.value = false;
  inkDrop();
  loadGraph();
}

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
  const request = ++graphRequest;
  loading.value = true;
  errorMessage.value = "";
  summary.value = null;
  graph.value = null;
  try {
    const g = await buildGraph(id);
    if (request !== graphRequest) return;
    if (g.error) {
      errorMessage.value = g.error;
      return;
    }
    graph.value = g;
    activePaperId.value = id;
    inkDrop();
    loading.value = false; // Mount the graph without waiting for the independent summary.
    // 摘要独立加载, 失败不影响图
    try {
      const s = await summarizePaper(id);
      if (request === graphRequest && !s.error) summary.value = s;
    } catch {
      /* 摘要降级缺失不阻塞 */
    }
  } catch (err) {
    if (request === graphRequest) errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    if (request === graphRequest) loading.value = false;
  }
}

function renderChart(g: CitationGraph) {
  if (isMobile.value || !chartContainer.value || !g.nodes.length) return;
  // loading 分支会销毁并重建容器；旧实例不能复用到新的 DOM。
  if (chart && chart.getDom() !== chartContainer.value) {
    chart.dispose();
    chart = null;
  }
  if (!chart) chart = echarts.init(chartContainer.value);
  const citationLogs = g.nodes
    .map((node) => node.citationCount)
    .filter((count): count is number => typeof count === "number" && count >= 0)
    .map((count) => Math.log1p(count));
  const minCitationLog = citationLogs.length ? Math.min(...citationLogs) : 0;
  const maxCitationLog = citationLogs.length ? Math.max(...citationLogs) : 1;
  const citationColor = (count?: number) => {
    if (count == null || count < 0) return "#aaa9a2";
    const value = Math.log1p(count);
    const ratio = maxCitationLog === minCitationLog
      ? 0.5
      : (value - minCitationLog) / (maxCitationLog - minCitationLog);
    const light = [253, 232, 230];
    const dark = [143, 29, 24];
    const rgb = light.map((channel, index) =>
      Math.round(channel + (dark[index] - channel) * ratio)
    );
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
  };
  chart.setOption({
    animationDuration: 400,
    tooltip: {
      trigger: "item",
      renderMode: "richText",
      formatter: (params: any) => {
        if (params.dataType !== "node") return "引用关系";
        const node = g.nodes.find((item) => item.paperId === params.data?.id);
        if (!node) return params.name ?? "";
        const level = node.depth === 0 ? "当前论文" : `第 ${node.depth} 层引用`;
        const citations = node.citationCount == null ? "被引量：暂无数据" : `被引量：${node.citationCount.toLocaleString()}`;
        return `${node.title ?? node.paperId}${node.year ? `\n${node.year}` : ""}\n${citations}\n${level}${node.preference_reason ? `\n偏好：${node.preference_reason}` : ""}`;
      },
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true, // 滚轮缩放 + 拖拽平移
        force: { repulsion: 220, edgeLength: 90 },
        // hover 时无关节点降至低透明度, 仅高亮关联航路
        emphasis: { focus: "adjacency", lineStyle: { color: "#0f5c5c", width: 2, type: "solid" } },
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
          name: i === 0 ? `你在这里 · ${activeTitle.value || n.title || "当前论文"}` : n.title ?? n.paperId,
          // 中心是坐标钉；第二层缩小并弱化，避免大图喧宾夺主。
          symbol: i === 0 ? "pin" : "circle",
          symbolSize: i === 0 ? 42 : (n.preference_score ?? 0) > 0 ? 18 : n.depth === 2 ? 8 : 13,
          label: { show: i === 0 || (n.preference_score ?? 0) > 0 || n.depth !== 2 },
          itemStyle:
            i === 0
              ? {
                  color: "#0f5c5c",
                  // 中心光晕用 box-shadow, 不用 filter: blur(防性能问题)
                  shadowBlur: 14,
                  shadowColor: "rgba(15, 92, 92, 0.45)",
                }
              : { color: citationColor(n.citationCount), borderColor: (n.preference_score ?? 0) > 0 ? "#2c5f5d" : "transparent", borderWidth: (n.preference_score ?? 0) > 0 ? 3 : 0 },
        })),
        // 引用 = 航路: 虚线
        links: g.edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: {
            color: e.depth === 2 ? "#b7b7af" : "#8a8a82",
            width: e.depth === 2 ? 0.75 : 1,
            type: "dashed",
          },
        })),
      },
    ],
  });
  // 点击节点 = 航行至该城邦(下钻为新中心)
  chart.off("click");
  chart.on("click", (params: unknown) => {
    const p = params as { dataType?: string; data?: { id?: string; name?: string } | null };
    if (p.dataType === "node" && p.data?.id && p.data.id !== activePaperId.value) {
      paperId.value = p.data.id;
      activeTitle.value = p.data.name ?? "";
      loadGraph(p.data.id);
    }
  });
}

// 移动端/无图时的列表退化
function drill(id: string, title?: string) {
  paperId.value = id;
  activeTitle.value = title ?? "";
  inkDrop();
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

    <form class="searchbar" role="search" @submit.prevent="activeTitle = ''; loadGraph()">
      <input
        v-model="paperId"
        type="search"
        placeholder="输入论文坐标（paperId），如 arXiv:1706.03762"
        aria-label="论文 ID"
      />
      <button type="submit">定位</button>
    </form>

    <!-- 关键词找论文入口 -->
    <div class="paper-search">
      <button type="button" class="paper-search-toggle" @click="showSearch = !showSearch">
        {{ showSearch ? "收起 ▴" : "没有坐标？按关键词找论文 ▾" }}
      </button>
      <Transition name="expand">
        <div v-if="showSearch" class="paper-search-panel">
        <form class="paper-search-bar" @submit.prevent="doSearchPapers">
          <input v-model="searchQuery" type="search" placeholder="输入论文关键词，如 transformer" aria-label="论文关键词" />
          <button type="submit" :disabled="searching">{{ searching ? "寻找中…" : "寻找" }}</button>
        </form>
        <p v-if="searchError" class="paper-search-err" role="alert">{{ searchError }}</p>
        <ul v-if="searchResults.length" class="paper-results">
          <li v-for="p in searchResults" :key="p.paperId">
            <button type="button" class="paper-result" @click="pickPaper(p)">
              <span class="paper-result-title">{{ p.title ?? p.paperId }}</span>
              <span v-if="p.year" class="paper-result-year mono">{{ p.year }}</span>
            </button>
          </li>
        </ul>
        <p v-else-if="!searching && !searchError && searchResults.length === 0 && searched" class="dim-note">没有找到相关论文</p>
        </div>
      </Transition>
    </div>

    <LoadingState v-if="loading" :rows="4" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <template v-else-if="graph">
      <p class="graph-meta">
        <span class="mono">{{ activePaperId }}</span>
        <span v-if="activeTitle" class="graph-title">· {{ activeTitle }}</span>
        · {{ graph.nodes.length - 1 }} 个关联节点 · {{ graph.edges.length }} 条航路 · 两层引用
        <span class="drill-hint">点击城邦航行至该处</span>
      </p>

      <p v-if="graph.personalization" class="preference-note" role="status">{{ graph.personalization.note }}</p>
      <!-- 桌面: 图纸化力导向图 -->
      <div v-if="!isMobile" class="chart-frame">
        <div ref="chartContainer" class="chart" aria-label="论文引用关系图"></div>

        <!-- 罗盘 -->
        <svg class="compass" viewBox="0 0 60 60" aria-hidden="true">
          <circle cx="30" cy="30" r="26" fill="none" stroke="#8b8b84" stroke-width="1" />
          <path d="M30 8 L34 30 L30 26 L26 30 Z" fill="#2c5f5d" />
          <path d="M30 52 L26 30 L30 34 L34 30 Z" fill="none" stroke="#8b8b84" stroke-width="1" />
          <text x="30" y="7" text-anchor="middle" font-size="8" fill="#8b8b84" font-family="serif">N</text>
        </svg>

        <!-- 图例 -->
        <div class="map-legend" aria-hidden="true">
          <span class="lg"><i class="lg-pin"></i>你在这里</span>
          <span class="lg citation-scale"><span>低被引</span><i></i><span>高被引</span></span>
          <span class="lg"><i class="lg-unknown"></i>暂无数据</span>
          <span v-if="graph.personalization?.applied" class="lg">◎ 偏好匹配</span>
          <span class="lg"><i class="lg-route"></i>引用航路</span>
        </div>
      </div>

      <!-- 移动端: 航线列表 -->
      <ul v-else class="node-list">
        <li v-for="n in graph.nodes.slice(1)" :key="n.paperId">
          <button type="button" class="node-link" @click="drill(n.paperId, n.title)">
            <span class="node-title">{{ n.title ?? n.paperId }}<small v-if="n.preference_reason"> · {{ n.preference_reason }}</small></span>
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
            aria-label="打开 PDF"
          >
            <SealStamp variant="seal" text="PDF" :subtext="summary.openAccessPdf.license" size="md" />
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

    <div v-else class="empty-invite">
      <SealStamp variant="idle" text="待探" />
      <p>输入 paperId 开始探索 —— 图谱会像星图一样展开</p>
    </div>

    <FeedbackFab
      :open="feedbackOpen"
      :on-submit="submitFeedback"
      @toggle="feedbackOpen = !feedbackOpen"
    />
  </section>
</template>

<style scoped>
.preference-note { color: var(--color-teal); font-size: 12px; line-height: 1.6; }
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
  gap: 0.5rem;
  font-size: 12.5px;
  color: var(--color-ink-muted);
  border-bottom: 1px solid var(--color-line);
  padding-bottom: 0.6rem;
  margin-bottom: 1rem;
  overflow: hidden;
}

.graph-title {
  color: var(--color-ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 40ch;
}

.drill-hint {
  margin-left: auto;
  font-size: 11.5px;
  flex-shrink: 0;
}

/* 关键词面板展开/收起过渡 */
.expand-enter-active,
.expand-leave-active {
  transition: opacity 0.22s ease, transform 0.22s var(--ease-out);
  transform-origin: top;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  transform: translateY(-6px) scaleY(0.96);
}

/* 图纸框: 双线边框 + 经纬网格底纹 */
.chart-frame {
  position: relative;
  padding: 6px;
  border: 1px solid var(--color-ink-muted);
  border-radius: 2px;
  background: var(--color-card);
}

.chart {
  width: 100%;
  height: 440px;
  border: 1px solid var(--color-line);
  /* 经纬网格: 两组 hairline, 不是渐变色块 */
  background-image:
    repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(28, 28, 26, 0.05) 39px, rgba(28, 28, 26, 0.05) 40px),
    repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(28, 28, 26, 0.05) 39px, rgba(28, 28, 26, 0.05) 40px);
}

.compass {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 52px;
  height: 52px;
  background: rgba(250, 250, 247, 0.85);
  border-radius: 50%;
  pointer-events: none;
}

.map-legend {
  position: absolute;
  left: 14px;
  bottom: 12px;
  display: flex;
  gap: 1rem;
  padding: 0.35rem 0.7rem;
  background: rgba(250, 250, 247, 0.9);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  font-size: 11.5px;
  color: var(--color-ink-soft);
  pointer-events: none;
}

.lg {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.lg-pin {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 9px solid var(--color-teal);
}

.lg-city {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-ink);
}

.lg-unknown {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #aaa9a2;
}

.citation-scale i {
  width: 48px;
  height: 7px;
  border-radius: 999px;
  background: linear-gradient(90deg, #fde8e6, #8f1d18);
}

.lg-route {
  width: 16px;
  border-top: 1px dashed var(--color-ink-muted);
}

/* 关键词找论文 */
.paper-search {
  max-width: 640px;
  margin: -1.25rem auto 2rem;
  text-align: center;
}

.paper-search-toggle {
  border: none;
  background: transparent;
  color: var(--color-teal);
  font-size: 13px;
  cursor: pointer;
  min-height: 44px;
}

.paper-search-panel {
  margin-top: 0.5rem;
  padding: 1rem 1.25rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  text-align: left;
}

.paper-search-bar {
  display: flex;
  gap: 0.5rem;
}

.paper-search-bar input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 0 0.75rem;
  font-size: 14px;
  background: var(--color-paper);
  outline: none;
}

.paper-search-bar input:focus {
  border-color: var(--color-teal);
}

.paper-search-bar button {
  min-height: 44px;
  padding: 0 1.1rem;
  border: none;
  border-radius: 2px;
  background: var(--color-teal);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.paper-search-err {
  margin: 0.6rem 0 0;
  font-size: 13px;
  color: var(--color-seal);
}

.paper-results {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
}

.paper-results li {
  border-top: 1px solid var(--color-line);
}

.paper-result {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  min-height: 44px;
  padding: 0.6rem 0.25rem;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.paper-result-title {
  font-size: 14px;
  color: var(--color-ink);
  line-height: 1.5;
}

.paper-result:hover .paper-result-title {
  color: var(--color-teal);
}

.paper-result-year {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.dim-note {
  margin: 0.75rem 0 0;
  font-size: 13px;
  color: var(--color-ink-muted);
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

/* 方形白文朱砂 PDF 钤印 */
.pdf-seal {
  flex-shrink: 0;
  display: inline-flex;
  text-decoration: none;
}

.pdf-seal:hover .seal-stamp {
  transform: rotate(var(--seal-rotate, 0deg)) scale(1.05);
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

/* editorial 首字下沉: 摘要第一段的开篇字母 */
.abstract-para:first-of-type::first-letter {
  font-family: var(--font-serif);
  font-size: 2.7em;
  font-weight: 600;
  line-height: 1;
  float: left;
  padding: 0.06em 0.12em 0 0;
  color: var(--color-teal);
}

.abstract-para.dim {
  color: var(--color-ink-muted);
}

.empty-invite {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  text-align: center;
  color: var(--color-ink-muted);
  margin: 3rem 0 0;
  font-size: 14px;
}

.empty-invite p {
  margin: 0;
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
