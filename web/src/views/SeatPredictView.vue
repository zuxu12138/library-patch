<script setup lang="ts">
import * as echarts from "echarts";
import { computed, nextTick, ref } from "vue";
import { predictSeats, sendFeedback } from "../api/seat";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const weekday = ref(1);
const hour = ref(14);
const loading = ref(false);
const errorMessage = ref("");
const realtimeAvailable = ref(true);
const chartContainer = ref<HTMLDivElement | null>(null);
const hasResult = ref(false);
const feedbackOpen = ref(false);
let chart: echarts.ECharts | null = null;

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const weekdayLabel = computed(() => `周${WEEKDAYS[weekday.value - 1]}`);

async function predict() {
  loading.value = true;
  errorMessage.value = "";
  hasResult.value = false;
  try {
    const prediction = await predictSeats(weekday.value, hour.value);
    realtimeAvailable.value = prediction.realtime_available;
    hasResult.value = true;
    await nextTick();
    if (chartContainer.value) {
      if (!chart) chart = echarts.init(chartContainer.value);
      chart.setOption({
        animationDuration: 600,
        grid: { left: 48, right: 20, top: 24, bottom: 32 },
        tooltip: { trigger: "axis", valueFormatter: (v: number) => `${v}%` },
        xAxis: {
          type: "category",
          data: prediction.ranking.map((r) => r.area_name),
          axisLabel: { color: "#64748b", fontSize: 12, interval: 0 },
          axisLine: { lineStyle: { color: "#e2e8f0" } },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          name: "占用率",
          max: 100,
          nameTextStyle: { color: "#64748b" },
          axisLabel: { color: "#94a3b8", fontSize: 12, formatter: "{value}%" },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        series: [
          {
            type: "bar",
            barWidth: "50%",
            data: prediction.ranking.map((r) => ({
              value: Math.round(r.avg_occupancy_rate * 100),
              itemStyle: {
                color:
                  r.avg_occupancy_rate < 0.5
                    ? "#16a34a"
                    : r.avg_occupancy_rate < 0.8
                      ? "#f59e0b"
                      : "#c8102e",
              },
            })),
            label: {
              show: true,
              position: "top",
              color: "#64748b",
              fontSize: 12,
              formatter: "{c}%",
            },
          },
        ],
      });
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  await sendFeedback(text);
  feedbackOpen.value = false;
}
</script>

<template>
  <section class="seat-predict">
    <header class="page-head">
      <h1 class="page-title">座位预测</h1>
      <p class="page-sub">按历史占用率估算，越空的区域排越前</p>
    </header>

    <form @submit.prevent="predict" class="controls">
      <label class="field">
        <span class="field-label">星期</span>
        <select v-model.number="weekday">
          <option v-for="d in 7" :key="d" :value="d">周{{ WEEKDAYS[d - 1] }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field-label">时段</span>
        <input v-model.number="hour" type="number" min="0" max="23" step="1" />
        <span class="field-unit">时</span>
      </label>
      <button type="submit" class="submit">预测</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <template v-else-if="hasResult">
      <div class="realtime-line">
        <span class="lamp" :class="{ off: !realtimeAvailable }" aria-hidden="true"></span>
        <span v-if="realtimeAvailable">已结合实时占用校正</span>
        <span v-else>实时数据暂不可用，以下为历史平均占用率</span>
      </div>
      <div ref="chartContainer" class="chart" aria-label="各区域占用率条形图"></div>
      <p class="hint">估算时段：{{ weekdayLabel }} {{ hour }}:00</p>
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

.controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.75rem 1.5rem;
  align-items: flex-end;
  margin-bottom: 1.5rem;
}

.field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.field-label {
  font-size: 14px;
  color: var(--ink-soft);
}

.field select,
.field input {
  padding: 0.5rem 0.65rem;
  border: 1.5px solid var(--line);
  border-radius: 8px;
  background: var(--card);
}

.field input {
  width: 4.4rem;
}

.field select:focus,
.field input:focus {
  outline: none;
  border-color: var(--dut-blue);
  box-shadow: 0 0 0 3px rgba(0, 61, 165, 0.1);
}

.field-unit {
  font-size: 14px;
  color: var(--ink-muted);
}

.submit {
  padding: 0.55rem 1.4rem;
  border: none;
  border-radius: 8px;
  background: var(--dut-blue);
  color: #fff;
  font-size: var(--fs-body);
  font-weight: 600;
  transition: background 0.15s ease;
}

.submit:hover {
  background: var(--dut-blue-bright);
}

.realtime-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 14px;
  color: var(--ink-soft);
}

.lamp {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--available);
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.18);
}

.lamp.off {
  background: var(--unavailable);
  box-shadow: none;
}

.chart {
  width: 100%;
  height: 340px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

.hint {
  margin: 0.75rem 0 0;
  text-align: center;
  font-size: 13px;
  color: var(--ink-muted);
}
</style>
