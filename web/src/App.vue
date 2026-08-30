<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import BookShell from "./components/BookShell.vue";
import { pendingRequests } from "./api/loading";
import { CHAPTERS, flipCount, flipLock, setSoundPref, soundPref } from "./book/book";
import { initInkBackground } from "./ink/ink";

// 活水墨背景: 一幅永远「将干未干」的水墨画
const inkCanvas = ref<HTMLCanvasElement | null>(null);
onMounted(() => {
  if (inkCanvas.value) initInkBackground(inkCanvas.value);
});

// 启动 splash: 编目卡片式入场, 最短停留 900ms 避免闪烁
const splash = ref(true);
onMounted(() => {
  window.setTimeout(() => (splash.value = false), 900);
});

// 滚动感知: 头部从「印在桌面上」变为「浮起一层」
const scrolled = ref(false);
function onScroll() {
  scrolled.value = window.scrollY > 8;
}
onMounted(() => {
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
});
onBeforeUnmount(() => window.removeEventListener("scroll", onScroll));

// 翻页音效: 首次翻页后提示一次; 开关持久化, 不自动播放
const soundHint = ref(false);
watch(flipCount, (n) => {
  if (n > 0 && soundPref.value === "unset") soundHint.value = true;
});
function answerSoundHint(on: boolean) {
  setSoundPref(on ? "on" : "off");
  soundHint.value = false;
}
function toggleSound() {
  setSoundPref(soundPref.value === "on" ? "off" : "on");
  soundHint.value = false;
}
</script>

<template>
  <!-- 活水墨背景: 远山墨意 + 墨滴洇开(事件触发), canvas 单层,
       pointer-events 不穿透; reduced-motion/低核设备自动降级 -->
  <canvas ref="inkCanvas" class="ink-canvas" aria-hidden="true"></canvas>

  <!-- 启动 splash: 翻开这本书 -->
  <Transition name="splash">
    <div v-if="splash" class="splash" aria-hidden="true">
      <div class="splash-card">
        <span class="splash-rule"></span>
        <strong>大连理工大学图书馆</strong>
        <span class="splash-sub">智慧服务 · 翻阅中</span>
      </div>
    </div>
  </Transition>

  <header class="site-head" :class="{ scrolled }">
    <div class="head-inner">
      <div class="brand">
        <span class="brand-rule" aria-hidden="true"></span>
        <span class="brand-name">
          <strong>大连理工大学图书馆</strong>
          <span class="brand-sub">智慧服务</span>
        </span>
      </div>

      <nav class="nav" :class="{ locked: flipLock }" aria-label="章节导航">
        <RouterLink
          v-for="c in CHAPTERS"
          :key="c.path"
          :to="c.path"
          class="nav-link"
        >
          <span class="nav-no" aria-hidden="true">{{ c.no }}</span>{{ c.cn }}
        </RouterLink>

        <!-- 翻页音效开关 -->
        <button
          type="button"
          class="sound-toggle"
          :class="{ on: soundPref === 'on' }"
          :aria-pressed="soundPref === 'on'"
          :title="soundPref === 'on' ? '关闭翻页音效' : '开启翻页音效'"
          @click="toggleSound"
        >
          <svg viewBox="0 0 24 24" fill="none" width="16" height="16" aria-hidden="true">
            <path d="M4 9v6h4l5 4V5L8 9H4z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
            <path v-if="soundPref === 'on'" d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            <path v-else d="M16 9l5 6M21 9l-5 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
        </button>
      </nav>
    </div>
    <!-- 任何请求进行中: 顶部细线「翻阅中」 -->
    <div class="progress-line" :class="{ active: pendingRequests > 0 }" aria-hidden="true"></div>
  </header>

  <!-- 整站即一本书: 翻页引擎接管章节切换 -->
  <BookShell />

  <footer class="site-foot">© 2026 大连理工大学图书馆 · 翻到书页边缘或使用 ← → 键翻页</footer>

  <!-- 翻页音效一次性提示 -->
  <Transition name="hint">
    <div v-if="soundHint" class="sound-hint" role="status">
      <span>可以开启轻轻的翻页音效</span>
      <button type="button" class="hint-yes" @click="answerSoundHint(true)">开启</button>
      <button type="button" class="hint-no" @click="answerSoundHint(false)">不了</button>
    </div>
  </Transition>
</template>

<style scoped>
/* 活水墨画布: 铺在桌面之上、书页之下 */
.ink-canvas {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

/* ---------- 外壳 ---------- */
.site-head {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  height: var(--nav-h);
  background: var(--color-paper);
  border-bottom: 1px solid transparent;
  transition: border-color 0.25s ease, background 0.25s ease;
}

.site-head.scrolled {
  background: var(--color-paper);
  border-bottom-color: var(--color-line);
}

.head-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  max-width: var(--measure);
  height: 100%;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}

.brand-rule {
  flex-shrink: 0;
  width: 3px;
  height: 22px;
  background: var(--color-teal);
}

.brand-name {
  display: flex;
  align-items: baseline;
  gap: 0.55rem;
  white-space: nowrap;
}

.brand-name strong {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--color-ink);
}

.brand-sub {
  font-size: 12px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
}

/* 章节导航: 等宽编号 + 滑动下划线 */
.nav {
  display: flex;
  align-items: center;
  gap: 1.75rem;
  flex-shrink: 0;
}

.nav-link {
  position: relative;
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  padding: 0.3rem 0;
  color: var(--color-ink-soft);
  font-size: 15px;
  white-space: nowrap;
  text-decoration: none;
  transition: color 0.2s ease;
}

.nav-no {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.05em;
  color: var(--color-ink-muted);
  transition: color 0.2s ease;
}

.nav-link::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  background: var(--color-teal);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.22s var(--ease-out);
}

.nav-link:hover {
  color: var(--color-ink);
}

.nav-link:hover .nav-no {
  color: var(--color-teal);
}

.nav-link:hover::after,
.nav-link.router-link-active::after {
  transform: scaleX(1);
}

.nav-link.router-link-active {
  color: var(--color-teal);
  font-weight: 500;
}

.nav-link.router-link-active .nav-no {
  color: var(--color-teal);
}

/* 翻页锁: 翻页进行中导航禁用 */
.nav.locked {
  pointer-events: none;
  opacity: 0.55;
}

/* 翻页音效开关 */
.sound-toggle {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  margin-left: -0.5rem;
  border: 1px solid transparent;
  border-radius: 2px;
  background: transparent;
  color: var(--color-ink-muted);
  cursor: pointer;
  transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.sound-toggle:hover {
  color: var(--color-teal);
  border-color: var(--color-line);
}

.sound-toggle.on {
  color: var(--color-teal);
  background: var(--color-teal-bg);
}

.site-foot {
  padding: 1.5rem;
  text-align: center;
  color: var(--color-ink-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
}

/* 启动 splash */
.splash {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  background: var(--color-desk);
  background-image: var(--paper-noise);
}

.splash-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 1.75rem 2.25rem;
  background: var(--color-paper);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  animation: breathe 1.6s ease-in-out infinite;
}

.splash-rule {
  width: 32px;
  height: 3px;
  background: var(--color-teal);
}

.splash-card strong {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.splash-sub {
  font-size: 12px;
  letter-spacing: 0.2em;
  color: var(--color-ink-muted);
}

.splash-leave-active {
  transition: opacity 0.3s ease;
}

.splash-leave-to {
  opacity: 0;
}

/* 顶部「翻阅中」细线 */
.progress-line {
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  width: 100%;
  background: var(--color-teal);
  transform: scaleX(0);
  transform-origin: left;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.progress-line.active {
  opacity: 1;
  animation: page-progress 1.4s var(--ease-out) infinite;
}

@keyframes page-progress {
  0% {
    transform: scaleX(0);
    transform-origin: left;
  }
  55% {
    transform: scaleX(1);
    transform-origin: left;
  }
  56% {
    transform-origin: right;
  }
  100% {
    transform: scaleX(0);
    transform-origin: right;
  }
}

/* 翻页音效提示 */
.sound-hint {
  position: fixed;
  left: 1.5rem;
  bottom: 1.5rem;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.9rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  font-size: 13px;
  color: var(--color-ink-soft);
}

.sound-hint button {
  border: 1px solid var(--color-line);
  border-radius: 2px;
  background: var(--color-paper);
  font-size: 12.5px;
  padding: 0.25rem 0.7rem;
  cursor: pointer;
  color: var(--color-ink);
  transition: border-color 0.15s ease, color 0.15s ease;
}

.sound-hint .hint-yes:hover {
  border-color: var(--color-teal);
  color: var(--color-teal);
}

.sound-hint .hint-no {
  color: var(--color-ink-muted);
}

.hint-enter-active,
.hint-leave-active {
  transition: opacity 0.25s ease, transform 0.25s var(--ease-out);
}

.hint-enter-from,
.hint-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 640px) {
  .brand-sub {
    display: none;
  }
  .brand-name strong {
    font-size: 14px;
  }
  .head-inner {
    padding: 0 1rem;
    gap: 0.75rem;
  }
  .nav {
    gap: 0.8rem;
  }
  .nav-link {
    font-size: 13px;
  }
  .nav-no {
    display: none;
  }
  .sound-toggle {
    width: 30px;
    height: 30px;
    margin-left: -0.25rem;
  }
  .sound-hint {
    left: 1rem;
    right: 1rem;
    bottom: 1rem;
  }
}
</style>
