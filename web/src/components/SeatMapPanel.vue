<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { fetchSeatMap, type SeatItem, type SeatMap } from "../api/seat";

const props = defineProps<{ mapId: string; areaName: string }>();
const emit = defineEmits<{ (e: "close"): void }>();

const loading = ref(true);
const refreshing = ref(false);
const errorMessage = ref("");
const map = ref<SeatMap | null>(null);
const zoom = ref(1);
const fullscreen = ref(false);

async function load(background = false) {
  if (background) refreshing.value = true;
  else loading.value = true;
  errorMessage.value = "";
  try {
    map.value = await fetchSeatMap(props.mapId);
  } catch (err) {
    // 静默刷新失败不清空已有图, 只在首次加载时占位报错
    if (!map.value) {
      errorMessage.value = err instanceof Error ? err.message : "座位平面图加载失败";
    }
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

onMounted(load);
// 平面图展开期间每 60s 静默刷新, 座位状态(可约/已约/占用)随真实数据更新
const refreshTimer = window.setInterval(() => load(true), 60_000);
onUnmounted(() => window.clearInterval(refreshTimer));

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

// 座位四态: 可预约(空闲) / 已预约 / 占用 / 不可预约(闭馆或停用)
// 判定顺序敏感: "不可预约"含"预约"二字, 必须先判不可预约
type SeatState = "free" | "reserved" | "busy" | "unavailable";
function seatState(s: SeatItem): SeatState {
  const status = s.status ?? "";
  if (status.includes("不可预约")) return "unavailable";
  if (status.includes("已预约") || status.includes("预约成功")) return "reserved";
  return s.busy ? "busy" : "free";
}

const STATE_LABEL: Record<SeatState, string> = {
  free: "可预约",
  reserved: "已被预约",
  busy: "占用中",
  unavailable: "不可预约",
};

const counts = computed(() => {
  const c: Record<SeatState, number> = { free: 0, reserved: 0, busy: 0, unavailable: 0 };
  for (const s of map.value?.seats ?? []) c[seatState(s)]++;
  return c;
});

const isClosed = computed(() => map.value?.is_open === false);
const openHoursLabel = computed(() => {
  const [open, close] = map.value?.open_hours ?? [7, 22];
  return `${String(open).padStart(2, "0")}:00 – ${String(close).padStart(2, "0")}:00`;
});

function seatLabel(s: SeatItem): string {
  const state = seatState(s);
  const extra = s.status && s.status !== STATE_LABEL[state] && state !== "unavailable" ? ` · ${s.status}` : "";
  return `${s.seatNum} 号 · ${STATE_LABEL[state]}${extra}`;
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
      <span v-if="map" class="map-count mono">
        可约 {{ counts.free }}<template v-if="counts.reserved"> · 已约 {{ counts.reserved }}</template>
        <template v-if="counts.busy"> · 占用 {{ counts.busy }}</template>
        <template v-if="counts.unavailable"> · 不可约 {{ counts.unavailable }}</template>
         · 共 {{ map.count }}
      </span>
      <span v-if="map?.fetched_at" class="map-updated mono">{{ refreshing ? "刷新中…" : `更新于 ${map.fetched_at}` }}</span>
      <div class="map-actions">
        <button type="button" class="map-tool wide" :disabled="refreshing" @click="load(true)">刷新</button>
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
      <p v-if="isClosed" class="map-notice closed" role="status">闭馆中 · 图为闭馆快照，全部座位暂停预约，{{ openHoursLabel }} 恢复服务</p>
      <p v-else-if="counts.unavailable" class="map-notice" role="status">不可预约按占用统计；占用数不代表实际在座人数。</p>
      <div class="map-canvas">
      <svg :viewBox="viewBox" class="seat-map" role="img" :aria-label="`${areaName} 座位平面图`">
        <g v-for="s in map.seats" :key="s.seatId">
          <rect
            :x="s.x - dotR"
            :y="s.y - dotR"
            :width="dotR * 2"
            :height="dotR * 2"
            class="seat"
            :class="[seatState(s), { power: hasPower(s) }]"
          >
            <title>{{ seatLabel(s) }}{{ hasPower(s) ? " · 电源" : "" }}{{ s.seatType.includes("台灯") ? " · 台灯" : "" }}</title>
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
        <span class="lg"><i class="sw sw-free"></i>可预约</span>
        <span class="lg"><i class="sw sw-reserved"></i>已预约</span>
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

/* 已预约: 朱砂描边浅底, 与推荐角标同色系但面积受控 */
.seat.reserved {
  fill: #f5e3de;
  stroke: var(--color-seal);
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

.map-notice.closed {
  color: var(--color-seal);
  border: 1px dashed var(--color-seal);
  border-radius: 2px;
  padding: 0.45rem 0.8rem;
  text-align: center;
}

.map-updated {
  font-size: 11.5px;
  color: var(--color-ink-muted);
}

.sw-reserved {
  background: #f5e3de;
  border: 1px solid var(--color-seal);
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
