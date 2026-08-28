<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { predictSeats, sendFeedback, type SeatPrediction } from "../api/seat";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const now = new Date();
const weekday = ref(now.getDay() === 0 ? 7 : now.getDay());
const hour = ref(now.getHours());
const loading = ref(false);
const errorMessage = ref("");
const prediction = ref<SeatPrediction | null>(null);
const feedbackOpen = ref(false);

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
  loading.value = true;
  errorMessage.value = "";
  try {
    prediction.value = await predictSeats(weekday.value, hour.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
    prediction.value = null;
  } finally {
    loading.value = false;
  }
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
          aria-label="小时"
          @input="onTimeChange"
        />
        <span class="hour-label mono">{{ String(hour).padStart(2, "0") }}:00</span>
      </div>
      <p v-if="isNow" class="now-line-note">
        <span class="now-mark" aria-hidden="true"></span>当前时刻 · {{ weekdayLabel }}
      </p>
    </div>

    <!-- 降级横幅: 实时数据不可用时 -->
    <p v-if="prediction && !prediction.realtime_available" class="banner" role="status">
      实时座位数据暂不可达，以下为纯历史预测
    </p>

    <LoadingState v-if="loading && !prediction" :rows="5" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <ol v-else-if="prediction?.ranking.length" class="ranking">
      <li
        v-for="(r, i) in prediction.ranking"
        :key="r.area_name"
        class="rank-row rise-in"
        :style="{ animationDelay: `${i * 50}ms` }"
      >
        <span class="rank-no mono">{{ String(i + 1).padStart(2, "0") }}</span>
        <span v-if="i === 0" class="rec-badge">推荐</span>
        <div class="rank-main">
          <div class="rank-head">
            <span class="area-name">{{ r.area_name.replace(/\s*\d+\/\d+\s*$/, "") }}</span>
            <span v-if="r.free_now != null" class="free mono">当前空 {{ r.free_now }}/{{ r.total }}</span>
          </div>
          <div class="bar-track" role="img" :aria-label="`预测占用率 ${Math.round(r.avg_occupancy_rate * 100)}%`">
            <div
              class="bar-fill"
              :class="{ hot: r.avg_occupancy_rate >= 0.6 }"
              :style="{ width: `${Math.round(r.avg_occupancy_rate * 100)}%` }"
            ></div>
          </div>
          <p v-if="r.samples < 4" class="low-samples">历史样本少（{{ r.samples }} 次），预测置信度低</p>
        </div>
        <span class="rate mono">{{ Math.round(r.avg_occupancy_rate * 100) }}%</span>
      </li>
    </ol>

    <div v-else-if="prediction" class="empty-state">
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
  transition: color 0.15s ease, border-color 0.15s ease;
}

.weekday:hover {
  color: var(--color-ink);
}

.weekday.active {
  color: var(--color-teal);
  border-color: var(--color-teal);
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
  background: var(--color-line);
  border-radius: 1px;
  outline: none;
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

.now-mark {
  width: 1px;
  height: 12px;
  background: var(--color-teal);
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
  padding: 0.9rem 0.25rem;
  border-bottom: 1px solid var(--color-line);
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
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.bar-fill.hot {
  background: var(--color-ink-muted);
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
}
</style>
