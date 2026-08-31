<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { predictSeats, sendFeedback, type SeatPrediction } from "../api/seat";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";
import SeatMapPanel from "../components/SeatMapPanel.vue";
import SealStamp from "../components/SealStamp.vue";
import SeatSparkline from "../components/SeatSparkline.vue";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const LIB_NAMES: Record<string, string> = {
  bochuan: "伯川",
  lingxi: "令希",
  panjin: "盘锦",
  kaifaqu: "开发区",
};
const now = new Date();
const weekday = ref(now.getDay() === 0 ? 7 : now.getDay());
const hour = ref(now.getHours());
const loading = ref(false);
const errorMessage = ref("");
const prediction = ref<SeatPrediction | null>(null);
const feedbackOpen = ref(false);
const libFilter = ref(""); // "" = 全部
const expandedMap = ref<string | null>(null); // 展开平面图的 area_name

// 心跳时钟: 驱动 isNow / 闭馆态随真实时间翻转; 「当前时刻」页每 60s 静默刷新实时数据
const nowTick = ref(Date.now());
const tickTimer = window.setInterval(() => {
  nowTick.value = Date.now();
  if (isNow.value) predict(true);
}, 60_000);
onUnmounted(() => window.clearInterval(tickTimer));

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
  const d = new Date(nowTick.value);
  return weekday.value === (d.getDay() === 0 ? 7 : d.getDay()) && hour.value === d.getHours();
});

// 闭馆态: 后端按所选时段判定(07:00–22:00 开馆), 闭馆时无实时数据, 只展示历史规律
const isClosed = computed(() => prediction.value !== null && !prediction.value.is_open);
const openHoursLabel = computed(() => {
  const [open, close] = prediction.value?.open_hours ?? [7, 22];
  return `${String(open).padStart(2, "0")}:00 – ${String(close).padStart(2, "0")}:00`;
});
// 闭馆时的恢复提示: 凌晨闭馆 → 今早开馆; 晚间闭馆 → 明早开馆
const reopenLabel = computed(() => {
  if (!isNow.value) return "该时段为闭馆时间";
  const [open] = prediction.value?.open_hours ?? [7, 22];
  const today = new Date(nowTick.value).getHours() < open;
  return `${today ? "今日" : "明日"} ${String(open).padStart(2, "0")}:00 起恢复预约`;
});

// 时间滑杆防抖 300ms
let debounceTimer: number | undefined;
function onTimeChange() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => predict(), 300);
}

async function predict(background = false) {
  loading.value = true;
  errorMessage.value = "";
  if (!background) expandedMap.value = null; // 静默刷新保留用户展开的平面图
  try {
    prediction.value = await predictSeats(weekday.value, hour.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
    prediction.value = null;
  } finally {
    loading.value = false;
  }
}

function toggleMap(areaName: string, mapId: string | null) {
  if (!mapId) return;
  expandedMap.value = expandedMap.value === areaName ? null : areaName;
}

onMounted(predict);

async function submitFeedback(text: string) {
  return await sendFeedback(text);
}
</script>

<template>
  <section class="seat">
    <header class="page-head">
      <h1 class="page-title">座位预测</h1>
      <p class="page-sub">按历史规律与实时占用，挑一个最可能有位置的阅览室</p>
    </header>

    <!-- 时间轴: 星期 + 24h 滑杆 -->
    <div class="timeline">
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
        <span class="hour-label mono" :class="{ closed: isClosed }">{{ String(hour).padStart(2, "0") }}:00</span>
      </div>
      <p v-if="isNow" class="now-line-note">
        <span class="live-dot" aria-hidden="true"></span>当前时刻 · {{ weekdayLabel }}
      </p>
    </div>

    <!-- 闭馆态: 暂停服务说明, 不再展示实时占用(闭馆后座位系统返回全空假象) -->
    <div v-if="isClosed" class="closed-hero rise-in" role="status">
      <SealStamp variant="idle" text="闭馆" subtext="暂停服务" />
      <h2 class="closed-title">抱歉，座位预约服务已暂停</h2>
      <p class="closed-sub">每日开馆 {{ openHoursLabel }} · {{ reopenLabel }}</p>
      <p v-if="filteredRanking.length" class="closed-note">以下为该时段历史规律，供开馆后选座参考</p>
    </div>

    <!-- 降级横幅: 当前时刻且开馆, 但实时数据不可达时 -->
    <p v-if="prediction && isNow && prediction.is_open && !prediction.realtime_available" class="banner" role="status">
      实时座位数据暂不可达，以下为纯历史预测
    </p>

    <!-- 非当前时刻的开馆时段: 说明为何没有实时空闲数 -->
    <p v-else-if="prediction && !isNow && prediction.is_open" class="banner banner-note" role="status">
      实时空闲数仅在「当前时刻」展示，以下为该时段历史规律预测
    </p>

    <p v-if="prediction?.is_open && prediction?.realtime_available" class="banner banner-note" role="status">
      统计口径：已占用或不可预约均计入占用，按楼层汇总，优先使用每 5 分钟采集的最新数据；不代表实际在馆人数。
    </p>

    <p v-if="prediction?.personalization" class="banner" role="status">{{ prediction.personalization.note }}</p>
    <!-- 全馆实时汇总 + 分馆筛选(仅开馆且拿到实时数据时) -->
    <div v-if="hallSummary && prediction?.is_open" class="hall-bar">
      <span class="hall-total">
        可用空座 <strong class="mono">{{ hallSummary.free }}</strong
        ><span class="dim mono"> / {{ hallSummary.total }}</span>
        <span v-if="prediction?.fetched_at" class="hall-updated mono">更新于 {{ prediction.fetched_at }}</span>
        <button type="button" class="refresh-btn" :disabled="loading" @click="predict(true)">
          {{ loading ? "刷新中…" : "刷新" }}
        </button>
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
        <span v-if="i === 0 && !isClosed && r.avg_occupancy_rate < 1 && r.free_now !== 0" class="rec-badge">推荐</span>
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
          <div class="bar-track" role="img" :aria-label="`预测占用率 ${Math.round(r.avg_occupancy_rate * 100)}%`">
            <div
              class="bar-fill"
              :class="{ hot: r.avg_occupancy_rate >= 0.6 }"
              :style="{ width: `${Math.round(r.avg_occupancy_rate * 100)}%` }"
            ></div>
          </div>
          <p v-if="r.samples < 4" class="low-samples">历史样本少（{{ r.samples }} 次），预测置信度低</p>
          <p v-if="r.preference_reason" class="preference-note">{{ r.preference_reason }}</p>
          <!-- 座位平面图下钻 -->
          <SeatMapPanel
            v-if="expandedMap === r.area_name && r.map_id"
            :map-id="r.map_id"
            :area-name="r.area_name.replace(/\s*\d+\/\d+\s*$/, '')"
            @close="expandedMap = null"
          />
        </div>
        <SeatSparkline
          :area-name="r.area_name"
          :weekday="weekday"
          :hour="hour"
          :rate="r.avg_occupancy_rate"
          class="spark"
        />
        <span class="rate mono">{{ Math.round(r.avg_occupancy_rate * 100) }}%</span>
      </li>
    </ol>

    <div v-else-if="prediction" class="empty-state">
      <SealStamp variant="idle" text="无座" />
      <p class="empty-title">这个时段还没有数据</p>
      <p class="empty-sub">采集器正在攒历史，换个时段试试</p>
    </div>

    <FeedbackFab
      :open="feedbackOpen"
      :on-submit="submitFeedback"
      @toggle="feedbackOpen = !feedbackOpen"
    />
  </section>
</template>

<style scoped>
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

/* 所选时段在闭馆时间: 标签转墨色, 与闭馆 hero 呼应 */
.hour-label.closed {
  color: var(--color-ink-muted);
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

/* 统计口径是普通说明, 不用警示色 */
.banner-note {
  border-color: var(--color-line);
  color: var(--color-ink-muted);
}

/* 闭馆态: 闲章 + 说明, 页面主角 */
.closed-hero {
  max-width: 640px;
  margin: 0 auto 2rem;
  padding: 2.25rem 1.5rem 1.9rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.7rem;
}

.closed-title {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 0.3rem 0 0;
}

.closed-sub {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: 14px;
}

.closed-note {
  margin: 0.4rem 0 0;
  padding-top: 0.7rem;
  border-top: 1px solid var(--color-line);
  color: var(--color-ink-muted);
  font-size: 12.5px;
}

.hall-updated {
  margin-left: 0.6rem;
  font-size: 11.5px;
  color: var(--color-ink-muted);
}

.refresh-btn {
  margin-left: 0.5rem;
  min-height: 30px;
  padding: 0 0.7rem;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  background: var(--color-card);
  color: var(--color-teal);
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.refresh-btn:hover:not(:disabled) {
  border-color: var(--color-teal);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: default;
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
