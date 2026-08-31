<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { predictSeats, sendFeedback, type SeatPrediction } from "../api/seat";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";
import SeatMapPanel from "../components/SeatMapPanel.vue";
import SealStamp from "../components/SealStamp.vue";


const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const LIB_NAMES: Record<string, string> = {
  bochuan: "伯川",
  lingxi: "令希",
  panjin: "盘锦",
  kaifaqu: "开发区",
};
const mode = ref<"now" | "plan">("now");
let requestId = 0;
let refreshTimer: number;
const now = new Date();
const weekday = ref(now.getDay() === 0 ? 7 : now.getDay());
const hour = ref(now.getHours());
const loading = ref(false);
const errorMessage = ref("");
const prediction = ref<SeatPrediction | null>(null);
const feedbackOpen = ref(false);
const libFilter = ref(""); // "" = 全部
const expandedMap = ref<string | null>(null); // 展开平面图的 area_name

const libs = computed(() => {
  const seen = new Set<string>();
  for (const r of prediction.value?.ranking ?? []) {
    if (r.lib_code) seen.add(r.lib_code);
  }
  return [...seen];
});

const filteredRanking = computed(() => {
  const all = prediction.value?.ranking ?? [];
  return libFilter.value ? all.filter((r) => r.lib_code === libFilter.value) : all;
});

// 全馆实时汇总
const hallSummary = computed(() => {
  const rows = (prediction.value?.ranking ?? []).filter((r) => r.free_now != null && r.total != null);
  if (!rows.length) return null;
  return {
    free: rows.reduce((s, r) => s + (r.free_now ?? 0), 0),
    total: rows.reduce((s, r) => s + (r.total ?? 0), 0),
  };
});

const weekdayLabel = computed(() => `周${WEEKDAYS[weekday.value - 1]}`);
const isNow = computed(() => {
  const d = new Date();
  return weekday.value === (d.getDay() === 0 ? 7 : d.getDay()) && hour.value === d.getHours();
});

// 时间滑杆防抖 300ms
let debounceTimer: number | undefined;
function onTimeChange() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => predict(), 300);
}

async function predict() {
  const request = ++requestId;
  prediction.value = null;
  loading.value = true;
  errorMessage.value = "";
  expandedMap.value = null;
  try {
    const result = await predictSeats(weekday.value, hour.value, mode.value);
    if (request === requestId) prediction.value = result;
  } catch (err) {
    if (request !== requestId) return;
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
    prediction.value = null;
  } finally {
    if (request === requestId) loading.value = false;
  }
}

function toggleMap(areaName: string, mapId: string | null) {
  if (!mapId) return;
  expandedMap.value = expandedMap.value === areaName ? null : areaName;
}

onMounted(() => { predict(); refreshTimer = window.setInterval(() => { if (mode.value === 'now') predict(); }, 60000); });
onBeforeUnmount(() => { requestId++; clearInterval(refreshTimer); clearTimeout(debounceTimer); });
function updated(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '尚无记录'; }

async function submitFeedback(text: string) {
  return await sendFeedback(text);
}
</script>

<template>
  <section class="seat">
    <header class="page-head">
      <h1 class="page-title">座位预测</h1>
      <p class="page-sub">先查看现在可用的位置，再参考历史安排学习计划</p>
    </header>

    <div class="mode-tabs" role="group" aria-label="查看方式">
      <button :class="{active:mode==='now'}" @click="mode='now'; predict()">现在去 · 可用性推荐</button>
      <button :class="{active:mode==='plan'}" @click="mode='plan'; predict()">计划去 · 历史参考</button>
    </div>
    <!-- 时间轴: 星期 + 24h 滑杆 -->
    <div v-if="mode === 'plan'" class="timeline">
      <div class="weekdays" role="tablist" aria-label="星期">
        <button
          v-for="(w, i) in WEEKDAYS"
          :key="w"
          type="button"
          role="tab"
          class="weekday"
          :class="{ active: weekday === i + 1 }"
          :aria-selected="weekday === i + 1"
          @click="weekday = i + 1; onTimeChange()"
        >
          {{ w }}
        </button>
      </div>
      <div class="hour-row">
        <input
          v-model.number="hour"
          type="range"
          min="0"
          max="23"
          step="1"
          class="hour-slider"
          :style="{ '--fill': `${(hour / 23) * 100}%` }"
          aria-label="小时"
          @input="onTimeChange"
        />
        <span class="hour-label mono">{{ String(hour).padStart(2, "0") }}:00</span>
      </div>
      <p v-if="isNow" class="now-line-note">
        <span class="live-dot" aria-hidden="true"></span>当前时刻 · {{ weekdayLabel }}
      </p>
    </div>

    <p v-if="prediction" class="banner" role="status">{{ prediction.message }}</p>
    <p v-if="mode==='now' && prediction && !prediction.closed && !filteredRanking.some(r => r.recommendable)" class="banner" role="status">暂无确认可用座位。不可预约不等于有人，过期或未知状态不算空座。</p>
    <p v-if="prediction?.personalization" class="banner" role="status">{{ prediction.personalization.note }}</p>
    <!-- 全馆实时汇总 + 分馆筛选 -->
    <div v-if="prediction" class="hall-bar">
      <span v-if="hallSummary && mode==='now'" class="hall-total">
        可用空座 <strong class="mono">{{ hallSummary.free }}</strong
        ><span class="dim mono"> / {{ hallSummary.total }}</span>
      </span>
      <div class="lib-tabs" role="tablist" aria-label="分馆筛选">
        <button
          type="button"
          class="lib-tab"
          :class="{ active: libFilter === '' }"
          @click="libFilter = ''"
        >
          全部
        </button>
        <button
          v-for="lib in libs"
          :key="lib"
          type="button"
          class="lib-tab"
          :class="{ active: libFilter === lib }"
          @click="libFilter = lib"
        >
          {{ LIB_NAMES[lib] ?? lib }}
        </button>
      </div>
    </div>

    <LoadingState v-if="loading && !prediction" :rows="5" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <ol v-else-if="filteredRanking.length" class="ranking">
      <li
        v-for="(r, i) in filteredRanking"
        :key="r.area_name"
        class="rank-row rise-in"
        :style="{ animationDelay: `${i * 50}ms` }"
      >
        <span class="rank-no mono">{{ String(i + 1).padStart(2, "0") }}</span>
        <span v-if="i === 0 && r.recommendable" class="rec-badge">推荐</span>
        <div class="rank-main">
          <button
            type="button"
            class="rank-head rank-head-btn"
            :class="{ drillable: r.map_id }"
            @click="toggleMap(r.area_name, r.map_id)"
          >
            <span class="area-name">{{ r.area_name.replace(/\s*\d+\/\d+\s*$/, "") }}</span>
            <span class="rank-head-right">
              <span v-if="r.free_now != null" class="free mono">可用 {{ r.free_now }}/{{ r.total }}</span>
              <span v-if="r.map_id" class="map-hint">{{ expandedMap === r.area_name ? "收起地图 ▴" : "座位平面图 ▾" }}</span>
            </span>
          </button>
          <template v-if="mode==='now'">
            <p v-if="prediction?.closed" class="status-counts">已闭馆 · 22:00 起暂停推荐</p>
            <p class="status-counts" v-if="r.fresh">已占用 {{ r.occupied_now }} · 不可预约 {{ r.unavailable_now }} · 未知 {{ r.unknown_now }}</p>
            <p class="low-samples">采集于 {{ updated(r.updated_at) }}（北京时间）{{ prediction?.closed ? ' · 最近快照，不用于闭馆时段推荐' : r.fresh ? '' : ' · 数据已过期，可用情况未知' }}</p>
          </template>
          <template v-else>
            <p v-if="r.predicted_available != null" class="status-counts">历史平均可用约 {{ r.predicted_available }} 座 / {{ r.total }}</p>
            <p v-else class="low-samples">历史数据不足，暂不估算空位。</p>
            <p class="low-samples">同星期、同时段有效样本：{{ r.sample_days ?? 0 }} 个不同日期（不含当天）</p>
          </template>
          <p v-if="r.preference_reason" class="preference-note">{{ r.preference_reason }}</p>
          <!-- 座位平面图下钻 -->
          <SeatMapPanel
            v-if="expandedMap === r.area_name && r.map_id"
            :map-id="r.map_id"
            :closed="prediction?.closed"
            :planned="mode === 'plan'"
            :area-name="r.area_name.replace(/\s*\d+\/\d+\s*$/, '')"
            @close="expandedMap = null"
          />
        </div>
        <span class="rate mono">{{ mode==='now' ? (prediction?.closed ? '已闭馆' : r.free_now == null ? '未知' : r.free_now + ' 座可用') : (r.predicted_available == null ? '样本不足' : '历史参考') }}</span>
      </li>
    </ol>

    <div v-else-if="prediction" class="empty-state">
      <SealStamp variant="idle" text="无座" />
      <p class="empty-title">这个时段还没有数据</p>
      <p class="empty-sub">采集器正在积累可用性数据，请稍后刷新</p>
    </div>

    <FeedbackFab
      :open="feedbackOpen"
      :on-submit="submitFeedback"
      @toggle="feedbackOpen = !feedbackOpen"
    />
  </section>
</template>

<style scoped>
.mode-tabs { display:flex; justify-content:center; gap:12px; margin:20px 0; }
.mode-tabs button { padding:12px 18px; border:1px solid var(--color-line); background:var(--color-card); cursor:pointer; }
.mode-tabs button.active { background:var(--color-teal); color:white; }
.status-counts { font-size:13px; color:var(--color-ink-soft); margin:8px 0; }

.preference-note { color: var(--color-teal); font-size: 12px; }
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

/* 时间轴 */
.timeline {
  max-width: 640px;
  margin: 0 auto 2rem;
  padding: 1.25rem 1.5rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
}

.weekdays {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
}

.weekday {
  flex: 1;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: 2px;
  background: transparent;
  font-size: 14px;
  color: var(--color-ink-soft);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}

.weekday:hover {
  color: var(--color-ink);
  background: var(--color-paper);
}

.weekday.active {
  color: var(--color-teal);
  border-color: var(--color-teal);
  background: var(--color-teal-bg);
  font-weight: 600;
}

.hour-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.hour-slider {
  flex: 1;
  appearance: none;
  height: 2px;
  /* 已走过的时段用深青填满, 未到的还是纸线 */
  background: linear-gradient(to right, var(--color-teal) 0%, var(--color-teal) var(--fill, 0%), var(--color-line) var(--fill, 0%), var(--color-line) 100%);
  border-radius: 1px;
  outline: none;
  transition: background 0.1s linear;
}

.hour-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-teal);
  cursor: pointer;
  border: 3px solid var(--color-card);
}

.hour-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-teal);
  cursor: pointer;
  border: 3px solid var(--color-card);
}

.hour-label {
  flex-shrink: 0;
  font-size: 14px;
  color: var(--color-teal);
  min-width: 48px;
  text-align: right;
}

.now-line-note {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.75rem 0 0;
  font-size: 12px;
  color: var(--color-ink-muted);
}

/* 全馆汇总 + 分馆 tab */
.hall-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  max-width: 720px;
  margin: 0 auto 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-line);
}

.hall-total {
  font-size: 14px;
  color: var(--color-ink-soft);
}

.hall-total strong {
  font-size: 20px;
  color: var(--color-teal);
  font-weight: 600;
}

.hall-total .dim {
  color: var(--color-ink-muted);
  font-size: 13px;
}

.lib-tabs {
  display: flex;
  gap: 0.25rem;
}

.lib-tab {
  min-height: 36px;
  padding: 0.25rem 0.8rem;
  border: 1px solid transparent;
  border-radius: 2px;
  background: transparent;
  font-size: 13px;
  color: var(--color-ink-soft);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.lib-tab:hover {
  color: var(--color-ink);
}

.lib-tab.active {
  color: var(--color-teal);
  border-color: var(--color-teal);
}

.rank-head-btn {
  width: 100%;
  border: none;
  background: transparent;
  padding: 0;
  cursor: default;
  font: inherit;
  text-align: left;
}

.rank-head-btn.drillable {
  cursor: pointer;
}

.rank-head-btn.drillable:hover .area-name {
  color: var(--color-teal);
}

.rank-head-right {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.map-hint {
  font-size: 11.5px;
  color: var(--color-teal);
  white-space: nowrap;
}

/* 降级横幅 */
.banner {
  max-width: 640px;
  margin: 0 auto 1.25rem;
  padding: 0.6rem 1rem;
  border: 1px dashed var(--color-seal);
  border-radius: 2px;
  color: var(--color-seal);
  font-size: 13px;
  text-align: center;
}

/* 排名列表: 博物馆展签式 */
.ranking {
  list-style: none;
  margin: 0 auto;
  padding: 0;
  max-width: 720px;
}

.rank-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.9rem 0.6rem;
  margin: 0 -0.6rem;
  border-bottom: 1px solid var(--color-line);
  border-radius: 2px;
  transition: background 0.15s ease;
}

.rank-row:hover {
  background: var(--color-card);
}

.rank-no {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--color-ink-muted);
  padding-top: 2px;
  min-width: 24px;
}

.rec-badge {
  flex-shrink: 0;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--color-seal);
  border: 1px solid var(--color-seal);
  border-radius: 2px;
  padding: 0.1rem 0.4rem;
  margin-top: 1px;
}

.rank-main {
  flex: 1;
  min-width: 0;
}

.rank-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
}

.area-name {
  font-size: 15px;
  font-weight: 500;
}

.free {
  font-size: 12px;
  color: var(--color-ink-soft);
  white-space: nowrap;
}

.bar-track {
  margin-top: 0.45rem;
  height: 6px;
  background: var(--color-paper);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: var(--color-teal);
  transition: width 0.35s var(--ease-out), background 0.3s ease;
}

/* 占用率 ≥60%: 拥挤预警, 用克制的赭黄而非警报红 */
.bar-fill.hot {
  background: var(--color-warn);
}

.low-samples {
  margin: 0.35rem 0 0;
  font-size: 11.5px;
  color: var(--color-ink-muted);
}

.rate {
  flex-shrink: 0;
  font-size: 15px;
  color: var(--color-ink);
  padding-top: 1px;
  min-width: 42px;
  text-align: right;
}

.spark {
  margin-left: auto;
  padding-right: 0.5rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
}

.empty-title {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.empty-sub {
  margin: 0.4rem 0 0;
  color: var(--color-ink-soft);
  font-size: 14px;
}

@media (max-width: 640px) {
  .page-title {
    font-size: 1.7rem;
  }
  .rank-row {
    gap: 0.6rem;
  }
  .rank-head {
    flex-direction: column;
    gap: 0.1rem;
  }
  .spark {
    display: none;
  }
}
</style>
