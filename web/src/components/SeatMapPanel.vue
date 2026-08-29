<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { fetchSeatMap, type SeatItem, type SeatMap } from "../api/seat";

const props = defineProps<{ mapId: string; areaName: string }>();
const emit = defineEmits<{ (e: "close"): void }>();

const loading = ref(true);
const errorMessage = ref("");
const map = ref<SeatMap | null>(null);

onMounted(async () => {
  try {
    map.value = await fetchSeatMap(props.mapId);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "座位平面图加载失败";
  } finally {
    loading.value = false;
  }
});

// 归一化坐标到 viewBox(四周留白边)
const viewBox = computed(() => {
  if (!map.value?.seats.length) return "0 0 100 100";
  const xs = map.value.seats.map((s) => s.x);
  const ys = map.value.seats.map((s) => s.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = Math.max(maxX - minX, maxY - minY) * 0.06;
  return `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`;
});

// 座位点半径随楼层规模自适应(600 座的楼层点要小一点)
const dotR = computed(() => {
  if (!map.value?.seats.length) return 30;
  const xs = map.value.seats.map((s) => s.x);
  const span = Math.max(...xs) - Math.min(...xs);
  return Math.max(12, span / 90);
});

const freeCount = computed(() => map.value?.seats.filter((s) => !s.busy).length ?? 0);

function hasPower(s: SeatItem): boolean {
  return (s.seatType ?? "").includes("电源");
}
</script>

<template>
  <div class="map-panel">
    <div class="map-head">
      <span class="map-title">{{ areaName }} · 座位平面</span>
      <span v-if="map" class="map-count mono">空 {{ freeCount }} / {{ map.count }}</span>
      <button type="button" class="map-close" aria-label="收起平面图" @click="emit('close')">收起 ↑</button>
    </div>

    <div v-if="loading" class="skeleton map-skeleton"></div>
    <p v-else-if="errorMessage" class="map-error" role="alert">{{ errorMessage }}</p>

    <template v-else-if="map">
      <svg :viewBox="viewBox" class="seat-map" role="img" :aria-label="`${areaName} 座位平面图`">
        <g v-for="s in map.seats" :key="s.seatId">
          <rect
            :x="s.x - dotR"
            :y="s.y - dotR"
            :width="dotR * 2"
            :height="dotR * 2"
            class="seat"
            :class="{ busy: s.busy, free: !s.busy, power: hasPower(s) }"
          >
            <title>{{ s.seatNum }} 号 · {{ s.busy ? "占用" : "空闲" }}{{ hasPower(s) ? " · 电源" : "" }}{{ s.seatType.includes("台灯") ? " · 台灯" : "" }}</title>
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

      <div class="map-legend" aria-hidden="true">
        <span class="lg"><i class="sw sw-free"></i>空闲</span>
        <span class="lg"><i class="sw sw-busy"></i>占用</span>
        <span class="lg"><i class="sw sw-power"></i>电源座</span>
      </div>
    </template>
  </div>
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
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

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

.seat-map {
  display: block;
  width: 100%;
  max-height: 380px;
  background: var(--color-card);
  border: 1px solid var(--color-line);
}

.seat {
  stroke-width: 1;
  transition: opacity 0.15s ease;
}

.seat.free {
  fill: var(--color-card);
  stroke: var(--color-teal);
}

.seat.busy {
  fill: var(--color-line);
  stroke: var(--color-ink-muted);
}

.seat:hover {
  opacity: 0.7;
}

.power-dot {
  fill: var(--color-seal);
  pointer-events: none;
}

.map-legend {
  display: flex;
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
