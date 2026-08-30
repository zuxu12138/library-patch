<script setup lang="ts">
/** 书的装订与翻页编排。
    - 前翻: 当前页绕左装订线 0→-180° 掀开, 新页早已垫在底下(先翻页后加载)
    - 回翻: 目标页从 -180°→0° 盖回来, 前半程露出的是它的纸背
    - 角度插值走 rAF, 但每帧只写 --turn 这一个 CSS 自定义属性;
      所有光影/旋转都是 calc(var(--turn) ...) 推导, 不触发 layout/paint */
import { onBeforeUnmount, onMounted, ref, watch, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import BookPage from "./BookPage.vue";
import { chapterFor, flipLock, neighborOf, noteFlip, type Chapter } from "../book/book";
import { inkDrop, setInkAnchor } from "../ink/ink";

type Role = "under" | "flip-out" | "flip-in";
interface Leaf {
  path: string;
  comp: Component;
  role: Role;
}

const route = useRoute();
const router = useRouter();

const DURATION = 700; // 起步果断, 落页沉稳
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

const leaves = ref<Leaf[]>([]);
const flipping = ref(false);
const settledPath = ref("");
const turn = ref(0);
const bookEl = ref<HTMLDivElement | null>(null);

let raf = 0;
let dragCommitPath: string | null = null;

function routeComp(path: string): Component | null {
  const matched = router.resolve(path).matched;
  return (matched[0]?.components?.default as Component | undefined) ?? null;
}

/* easeInOutCubic = cubic-bezier(0.645, 0.045, 0.355, 1) */
function ease(p: number): number {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

function animateTurn(from: number, to: number, done: () => void) {
  cancelAnimationFrame(raf);
  const t0 = performance.now();
  const step = (t: number) => {
    const p = Math.min(1, (t - t0) / DURATION);
    turn.value = from + (to - from) * ease(p);
    if (p < 1) raf = requestAnimationFrame(step);
    else done();
  };
  raf = requestAnimationFrame(step);
}

/** 翻页落定: 收掉旧页, 100ms 后放行页内动画(「翻开 → 内容苏醒」)。
    count=false 用于触摸跟手后的弹回——没翻过去就不算一次翻页 */
function settle(path: string, count = true) {
  cancelAnimationFrame(raf);
  const keep = leaves.value.find((l) => l.path === path);
  if (keep) {
    keep.role = "under";
    leaves.value = [keep];
  }
  flipping.value = false;
  dragCommitPath = null;
  if (count) {
    noteFlip();
    // 翻页落定: 新页面的空白边缘洇开一滴淡墨
    inkDrop();
  }
  window.setTimeout(() => (settledPath.value = path), 100);
}

/** 翻页进行中又来了新导航: 立即落定当前页, 再启新翻页(防穿帮) */
function finishImmediate() {
  cancelAnimationFrame(raf);
  const keep = leaves.value[leaves.value.length - 1];
  keep.role = "under";
  leaves.value = [keep];
  flipping.value = false;
}

function mountInitial(path: string) {
  const comp = routeComp(path);
  if (!comp) return;
  leaves.value = [{ path, comp, role: "under" }];
  window.setTimeout(() => (settledPath.value = path), 100);
}

/** 摆出翻页层: forward = 旧页在上往外掀; back = 新页在上往回盖 */
function arrange(targetPath: string, direction: "forward" | "back") {
  const comp = routeComp(targetPath);
  if (!comp) return false;
  settledPath.value = "";
  const current = leaves.value[leaves.value.length - 1];
  if (direction === "forward") {
    current.role = "flip-out";
    leaves.value.push({ path: targetPath, comp, role: "under" });
    turn.value = 0;
  } else {
    current.role = "under";
    leaves.value.push({ path: targetPath, comp, role: "flip-in" });
    turn.value = 1;
  }
  flipping.value = true;
  return true;
}

function startFlip(targetPath: string, direction: "forward" | "back") {
  if (reduced.matches) {
    // 降级: 200ms 横向 slide + fade, 导航可用性保留
    const comp = routeComp(targetPath);
    if (!comp) return;
    settledPath.value = "";
    leaves.value = [{ path: targetPath, comp, role: "under" }];
    noteFlip();
    window.setTimeout(() => (settledPath.value = targetPath), 200);
    return;
  }
  if (!arrange(targetPath, direction)) return;
  if (direction === "forward") animateTurn(0, 1, () => settle(targetPath));
  else animateTurn(1, 0, () => settle(targetPath));
}

watch(
  () => route.path,
  (path, oldPath) => {
    if (!leaves.value.length) {
      mountInitial(path);
      return;
    }
    const from = chapterFor(oldPath);
    const to = chapterFor(path);
    if (!to || from?.path === to.path) return;
    // 触摸跟手翻页已摆好层并提交了路由: 直接从当前角度走完
    if (flipping.value && dragCommitPath === path) {
      const dir = to.index > (from?.index ?? to.index) ? "forward" : "back";
      dragCommitPath = null;
      if (dir === "forward") animateTurn(turn.value, 1, () => settle(path));
      else animateTurn(turn.value, 0, () => settle(path));
      return;
    }
    if (flipping.value) finishImmediate();
    startFlip(path, to.index > (from?.index ?? to.index) ? "forward" : "back");
  }
);

/* ---------- 翻页热区 / 键盘 ---------- */

function go(delta: 1 | -1) {
  if (flipping.value) return; // 翻页锁: 700ms 内禁止再触发
  const target = neighborOf(route.path, delta);
  if (target) void router.push(target.path);
}

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (e.key === "ArrowRight") go(1);
  else if (e.key === "ArrowLeft") go(-1);
}

/* ---------- 移动端: 屏幕左右边缘触摸跟手翻页 ---------- */

interface DragState {
  x0: number;
  active: boolean;
  direction: "forward" | "back";
  target: Chapter;
}
let drag: DragState | null = null;

function onTouchStart(e: TouchEvent) {
  if (flipping.value || reduced.matches || e.touches.length !== 1) return;
  const t = e.touches[0];
  const edge = 28;
  const w = window.innerWidth;
  if (t.clientX > edge && t.clientX < w - edge) return; // 只认左右边缘起势
  const direction = t.clientX <= edge ? "back" : "forward"; // 左缘向右拖=回翻, 右缘向左拖=前翻
  const target = neighborOf(route.path, direction === "forward" ? 1 : -1);
  if (!target) return;
  drag = { x0: t.clientX, active: false, direction, target };
}

function onTouchMove(e: TouchEvent) {
  if (!drag) return;
  const t = e.touches[0];
  const dx = t.clientX - drag.x0;
  if (!drag.active) {
    const want = drag.direction === "forward" ? dx < -10 : dx > 10;
    if (!want) {
      if (Math.abs(dx) > 10) drag = null; // 反向起手, 放弃
      return;
    }
    if (!arrange(drag.target.path, drag.direction)) {
      drag = null;
      return;
    }
    drag.active = true;
  }
  e.preventDefault(); // 跟手期间禁止页面滚动
  const w = bookEl.value?.clientWidth ?? window.innerWidth;
  const f = Math.min(1, Math.abs(dx) / w);
  turn.value = drag.direction === "forward" ? f : 1 - f; // rotateY 实时跟手
}

function onTouchEnd() {
  if (!drag) return;
  const d = drag;
  drag = null;
  if (!d.active) return;
  const turnedDeg = (d.direction === "forward" ? turn.value : 1 - turn.value) * 180;
  if (turnedDeg > 40) {
    // 超过 40°: 翻过去
    dragCommitPath = d.target.path;
    void router.push(d.target.path);
  } else {
    // 不足: 弹回原页
    const back = d.direction === "forward" ? 0 : 1;
    const path = route.path;
    animateTurn(turn.value, back, () => settle(path, false));
  }
}

onMounted(() => {
  mountInitial(route.path);
  setInkAnchor(bookEl.value); // 落点算法避开书页内容区
  window.addEventListener("keydown", onKeydown);
  const el = bookEl.value;
  el?.addEventListener("touchstart", onTouchStart, { passive: true });
  el?.addEventListener("touchmove", onTouchMove, { passive: false });
  el?.addEventListener("touchend", onTouchEnd, { passive: true });
});

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  window.removeEventListener("keydown", onKeydown);
  const el = bookEl.value;
  el?.removeEventListener("touchstart", onTouchStart);
  el?.removeEventListener("touchmove", onTouchMove);
  el?.removeEventListener("touchend", onTouchEnd);
});

const hasPrev = () => !!neighborOf(route.path, -1);
const hasNext = () => !!neighborOf(route.path, 1);

// 翻页锁同步到全局: 头部章节导航在翻页中禁用
watch(flipping, (v) => (flipLock.value = v), { immediate: true });
onBeforeUnmount(() => (flipLock.value = false));
</script>

<template>
  <div class="book-desk">
    <div
      ref="bookEl"
      class="book"
      :class="{ turning: flipping }"
      :style="{ '--turn': String(turn) }"
    >
      <div
        v-for="leaf in leaves"
        :key="leaf.path"
        class="leaf-wrap"
        :class="[leaf.role, { settled: settledPath === leaf.path }]"
      >
        <BookPage v-if="chapterFor(leaf.path)" :chapter="chapterFor(leaf.path)!" :turning="leaf.role !== 'under'">
          <component :is="leaf.comp" />
        </BookPage>
      </div>

      <!-- 翻页热区: 几乎不可见, hover 时露出深青细弧 -->
      <button
        v-if="hasPrev()"
        type="button"
        class="hot-zone left"
        :disabled="flipping"
        aria-label="翻到上一页"
        @click="go(-1)"
      ></button>
      <button
        v-if="hasNext()"
        type="button"
        class="hot-zone right"
        :disabled="flipping"
        aria-label="翻到下一页"
        @click="go(1)"
      ></button>
    </div>
  </div>
</template>

<style scoped>
.book-desk {
  padding: calc(var(--nav-h) + 1.75rem) 1rem 3rem;
}

/* 摊开的单页书: 最大 880px, 仅靠 1px 描边 + 4% 投影与桌面区分 */
.book {
  position: relative;
  width: min(880px, 100%);
  margin: 0 auto;
  perspective: 2400px;
}

.leaf-wrap {
  background: var(--color-paper);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  transform-style: preserve-3d;
}

.leaf-wrap.under {
  position: relative;
  z-index: 1;
}

/* 被盖住时随翻页角度呼吸的暗面(峰值在 90° 侧立瞬间) */
.leaf-wrap.under::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 5;
  background: #1c1c1a;
  opacity: calc(var(--turn, 0) * (1 - var(--turn, 0)) * 0.32);
  pointer-events: none;
}

/* 翻动中的页: 绕左装订线, 只动 transform */
.leaf-wrap.flip-out,
.leaf-wrap.flip-in {
  position: absolute;
  inset: 0;
  z-index: 2;
  overflow: hidden;
  transform-origin: left center;
  transform: rotateY(calc(var(--turn, 0) * -180deg));
  will-change: transform;
}

/* 翻动的页正面裁切在纸面范围内 */
.leaf-wrap.flip-out :deep(.face.front),
.leaf-wrap.flip-in :deep(.face.front) {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

/* 页内微交互门控: 落定前 .rise-in 一律压住, 落定 100ms 后苏醒 */
.leaf-wrap:not(.settled) :deep(.rise-in) {
  opacity: 0;
  animation: none;
}

/* 翻页热区 */
.hot-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  width: 48px;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.hot-zone.left {
  left: -8px;
}
.hot-zone.right {
  right: -8px;
}

.hot-zone::after {
  content: "";
  position: absolute;
  top: 50%;
  width: 12px;
  height: 64px;
  transform: translateY(-50%);
  border: 2px solid var(--color-teal);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.hot-zone.left::after {
  left: 12px;
  border-radius: 64px 0 0 64px;
  border-right: none;
}

.hot-zone.right::after {
  right: 12px;
  border-radius: 0 64px 64px 0;
  border-left: none;
}

.hot-zone:hover::after,
.hot-zone:focus-visible::after {
  opacity: 0.75;
}

/* 触屏设备不显示热区弧(用边缘手势) */
@media (hover: none) {
  .hot-zone {
    display: none;
  }
}

/* reduced-motion: 翻页退化为 200ms 横向 slide + fade */
@media (prefers-reduced-motion: reduce) {
  .leaf-wrap.under {
    animation: rm-slide 0.2s ease both;
  }
  .leaf-wrap.under::after {
    display: none;
  }
}

@keyframes rm-slide {
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (max-width: 640px) {
  .book-desk {
    padding: calc(var(--nav-h) + 0.75rem) 0.5rem 2rem;
  }
}
</style>
