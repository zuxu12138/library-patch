<script setup lang="ts">
/** 座位 24h 占用趋势 sparkline
 *  前端本地生成的示意曲线，非真实历史数据；
 *  用 areaName + weekday 做种子保证同区域同日确定性，
 *  再把当前 hour 对齐到接口返回的 rate。
 */
import { computed } from "vue";

const props = defineProps<{
  areaName: string;
  weekday: number;
  hour: number;
  rate: number;
}>();

const W = 96;
const H = 32;
const PAD = 3;

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

const points = computed(() => {
  const seed = `${props.areaName}#${props.weekday}`;
  const base = hash(seed);
  const hrs: number[] = [];
  for (let i = 0; i < 24; i++) {
    // 每日双峰: 上午 10 点、晚上 19 点，叠加低幅噪声
    const morning = Math.exp(-Math.pow(i - 10, 2) / 18);
    const evening = Math.exp(-Math.pow(i - 19, 2) / 24);
    const noise = hash(`${seed}:${i}`) * 0.22 - 0.11;
    let v = 0.25 + 0.35 * morning + 0.28 * evening + noise;
    v += (base - 0.5) * 0.12;
    hrs.push(Math.max(0.05, Math.min(0.95, v)));
  }
  // 把当前 hour 对齐到真实 rate
  hrs[props.hour] = props.rate;
  // 平滑左右邻点，避免尖角
  if (props.hour > 0) hrs[props.hour - 1] = hrs[props.hour - 1] * 0.6 + props.rate * 0.4;
  if (props.hour < 23) hrs[props.hour + 1] = hrs[props.hour + 1] * 0.6 + props.rate * 0.4;

  return hrs.map((v, i) => {
    const x = PAD + (i / 23) * (W - PAD * 2);
    const y = H - PAD - v * (H - PAD * 2);
    return { x, y, v };
  });
});

const linePath = computed(() => points.value.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" "));
const areaPath = computed(() => {
  const first = points.value[0];
  const last = points.value[points.value.length - 1];
  return `${linePath.value} L${last.x.toFixed(1)} ${H - PAD} L${first.x.toFixed(1)} ${H - PAD} Z`;
});
const current = computed(() => points.value[props.hour]);
</script>

<template>
  <svg
    class="seat-sparkline"
    :viewBox="`0 0 ${W} ${H}`"
    role="img"
    :aria-label="`${areaName} 24 小时占用趋势示意`"
  >
    <title>{{ areaName }} 24 小时占用趋势示意（当前 {{ Math.round(rate * 100) }}%）</title>
    <polygon :d="areaPath" class="spark-area" />
    <path :d="linePath" class="spark-line" fill="none" />
    <circle :cx="current.x.toFixed(1)" :cy="current.y.toFixed(1)" r="2.2" class="spark-dot" />
  </svg>
</template>

<style scoped>
.seat-sparkline {
  width: 96px;
  height: 32px;
  flex-shrink: 0;
}

.spark-area {
  fill: rgba(44, 95, 93, 0.08);
}

.spark-line {
  stroke: var(--color-teal);
  stroke-width: 1.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.spark-dot {
  fill: var(--color-teal);
}
</style>
