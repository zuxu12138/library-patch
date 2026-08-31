<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { fetchSeatMap, type SeatItem, type SeatMap } from "../api/seat";

const props = defineProps<{ mapId: string; areaName: string }>();
const emit = defineEmits<{ (e: "close"): void }>();

const loading = ref(true);
const errorMessage = ref("");
const map = ref<SeatMap | null>(null);
const zoom = ref(1);
const fullscreen = ref(false);

onMounted(async () => {
  try {
    map.value = await fetchSeatMap(props.mapId);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "座位平面图加载失败";
  } finally {
    loading.value = false;
  }
});

// 原始坐标边界；缩放时围绕平面中心收紧 viewBox。
const bounds = computed(() => {
  if (!map.value?.seats.length) return { minX: 0, minY: 0, width: 100, height: 100 };
  const xs = map.value.seats.map((s) => s.x);
  const ys = map.value.seats.map((s) => s.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = Math.max(maxX - minX, maxY - minY) * 0.055;
  return { minX: minX - pad, minY: minY - pad,
           width: maxX - minX + pad * 2, height: maxY - minY + pad * 2 };
});
const viewBox = computed(() => {
  const b = bounds.value;
  const width = b.width / zoom.value, height = b.height / zoom.value;
  return `${b.minX + (b.width - width) / 2} ${b.minY + (b.height - height) / 2} ${width} ${height}`;
});
function setZoom(next: number) { zoom.value = Math.min(3, Math.max(1, next)); }

// 座位点半径随楼层规模自适应(600 座的楼层点要小一点)
const dotR = computed(() => {
  if (!map.value?.seats.length) return 30;
  const xs = map.value.seats.map((s) => s.x);
  const span = Math.max(...xs) - Math.min(...xs);
  return Math.max(12, span / 90);
});

function isUnavailable(s: SeatItem): boolean {
  return (s.status ?? "").includes("不可预约");
}

const freeCount = computed(() => map.value?.seats.filter((s) => !s.busy && !isUnavailable(s)).length ?? 0);
const unavailableCount = computed(() => map.value?.seats.filter(isUnavailable).length ?? 0);

function seatLabel(s: SeatItem): string {
  if (isUnavailable(s)) return s.busy ? "计入占用 · 不可预约" : "计入占用 · 不可预约";
  return `${s.busy ? "系统标记占用" : "系统标记空闲"}${s.status ? ` · ${s.status}` : ""}`;
}

function hasPower(s: SeatItem): boolean {
  return (s.seatType ?? "").includes("电源");
}
</script>

<template>
  <Teleport to="body" :disabled="!fullscreen">
  <div class="map-panel" :class="{ fullscreen }">
    <div class="map-head">
      <span class="map-title">{{ areaName }} · 座位平面</span>
      <span v-if="map" class="map-count mono">可用 {{ freeCount }} · 占用 {{ map.count - freeCount }}（含不可预约 {{ unavailableCount }}） · 共 {{ map.count }}</span>
      <div class="map-actions">
        <button type="button" class="map-tool" aria-label="缩小" :disabled="zoom <= 1" @click="setZoom(zoom - 0.5)">−</button>
        <span class="zoom-value mono">{{ Math.round(zoom * 100) }}%</span>
        <button type="button" class="map-tool" aria-label="放大" :disabled="zoom >= 3" @click="setZoom(zoom + 0.5)">＋</button>
        <button type="button" class="map-tool wide" @click="fullscreen = !fullscreen">{{ fullscreen ? "退出大图" : "全屏查看" }}</button>
        <button type="button" class="map-close" aria-label="收起平面图" @click="fullscreen ? fullscreen = false : emit('close')">{{ fullscreen ? "关闭" : "收起 ↑" }}</button>
      </div>
    </div>

    <div v-if="loading" class="skeleton map-skeleton"></div>
    <p v-else-if="errorMessage" class="map-error" role="alert">{{ errorMessage }}</p>

    <template v-else-if="map">
      <p v-if="unavailableCount" class="map-notice" role="status">不可预约按占用统计；占用数不代表实际在座人数。</p>
      <div class="map-canvas">
      <svg :viewBox="viewBox" class="seat-map" role="img" :aria-label="`${areaName} 座位平面图`">
        <g v-for="s in map.seats" :key="s.seatId">
          <rect
            :x="s.x - dotR"
            :y="s.y - dotR"
            :width="dotR * 2"
            :height="dotR * 2"
            class="seat"
            :class="{ unavailable: isUnavailable(s), busy: s.busy && !isUnavailable(s), free: !s.busy && !isUnavailable(s), power: hasPower(s) }"
          >
            <title>{{ s.seatNum }} 号 · {{ seatLabel(s) }}{{ hasPower(s) ? " · 电源" : "" }}{{ s.seatType.includes("台灯") ? " · 台灯" : "" }}</title>
          </rect>
          <!-- 电源座位的角标 -->
          <circle
            v-if="hasPower(s)"
            :cx="s.x + dotR * 0.7"
            :cy="s.y - dotR * 0.7"
            :r="dotR * 0.28"
            class="power-dot"
          />
        </g>
      </svg>
      <div class="map-compass mono"><b>N</b><span>↑</span></div>
      </div>

      <div class="map-legend" aria-hidden="true">
        <span class="lg"><i class="sw sw-free"></i>空闲</span>
        <span class="lg"><i class="sw sw-busy"></i>占用</span>
        <span class="lg"><i class="sw sw-unavailable"></i>不可预约</span>
        <span class="lg"><i class="sw sw-power"></i>电源座</span>
      </div>
    </template>
  </div>
  </Teleport>
</template>

<style scoped>
.map-panel {
  margin: 0.35rem 0 0.75rem;
  padding: 0.9rem 1rem;
  background: var(--color-paper);
  border: 1px solid var(--color-line);
  border-radius: 2px;
}

.map-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.map-actions { margin-left: auto; display: flex; align-items: center; gap: .35rem; }
.map-tool { min-height: 30px; min-width: 30px; border: 1px solid var(--color-line); background: var(--color-card); color: var(--color-ink); cursor: pointer; }
.map-tool:disabled { opacity: .35; cursor: default; }
.map-tool.wide { padding: 0 .7rem; }
.zoom-value { min-width: 42px; text-align: center; font-size: 11px; }

.map-title {
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
}

.map-count {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.map-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--color-teal);
  font-size: 12.5px;
  cursor: pointer;
  min-height: 32px;
}

.map-skeleton {
  height: 200px;
}

.map-error {
  margin: 0.5rem 0;
  font-size: 13px;
  color: var(--color-seal);
}

.map-canvas { position: relative; overflow: hidden; border: 1px solid var(--color-line); background-color: #f7f3ea; background-image: linear-gradient(rgba(50,91,87,.06) 1px, transparent 1px), linear-gradient(90deg, rgba(50,91,87,.06) 1px, transparent 1px); background-size: 24px 24px; }
.seat-map {
  display: block;
  width: 100%;
  height: clamp(360px, 50vh, 560px);
  background: rgba(255,255,255,.42);
}

.seat {
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  rx: 5;
  transition: opacity 0.15s ease, filter .15s ease;
}

.seat.free {
  fill: var(--color-card);
  stroke: var(--color-teal);
}

.seat.busy {
  fill: var(--color-line);
  stroke: var(--color-ink-muted);
}

.seat.unavailable {
  fill: #eadbc5;
  stroke: #8a652f;
  stroke-dasharray: 5 3;
}

.map-notice {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.sw-unavailable {
  background: #eadbc5;
  border: 1px dashed #8a652f;
}

.seat:hover {
  opacity: .92;
  filter: drop-shadow(0 0 7px rgba(43,95,89,.6));
}

.power-dot {
  fill: var(--color-seal);
  pointer-events: none;
}

.map-compass { position: absolute; right: 14px; top: 12px; display: grid; justify-items: center; color: var(--color-teal); background: rgba(255,255,255,.8); border: 1px solid var(--color-line); padding: 5px 8px; }
.map-compass b { font-size: 10px; }
.map-compass span { font-size: 18px; line-height: 14px; }
.map-panel.fullscreen { position: fixed; inset: 22px; z-index: 120; margin: 0; padding: 1.2rem; box-shadow: 0 20px 80px rgba(20,25,24,.35); display: flex; flex-direction: column; background: var(--color-paper); }
.map-panel.fullscreen .map-canvas { flex: 1; min-height: 0; }
.map-panel.fullscreen .seat-map { height: 100%; max-height: none; }
@media (max-width: 700px) { .map-panel.fullscreen { inset: 0; } .map-actions { width: 100%; margin-left: 0; } .map-tool.wide { display: none; } }

.map-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  margin-top: 0.6rem;
  font-size: 12px;
  color: var(--color-ink-muted);
}

.lg {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.sw {
  display: inline-block;
  width: 10px;
  height: 10px;
}

.sw-free {
  border: 1px solid var(--color-teal);
  background: var(--color-card);
}

.sw-busy {
  background: var(--color-line);
  border: 1px solid var(--color-ink-muted);
}

.sw-power {
  position: relative;
  border: 1px solid var(--color-teal);
  background: var(--color-card);
}

.sw-power::after {
  content: "";
  position: absolute;
  top: -2px;
  right: -2px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-seal);
}
</style>
