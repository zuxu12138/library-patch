<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, RouterView } from "vue-router";
import { pendingRequests } from "./api/loading";

// 启动 splash: 编目卡片式入场, 最短停留 900ms 避免闪烁
const splash = ref(true);
onMounted(() => {
  window.setTimeout(() => (splash.value = false), 900);
});
</script>

<template>
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

  <header class="site-head">
    <div class="head-inner">
      <div class="brand">
        <span class="brand-rule" aria-hidden="true"></span>
        <span class="brand-name">
          <strong>大连理工大学图书馆</strong>
          <span class="brand-sub">智慧服务</span>
        </span>
      </div>

      <nav class="nav" aria-label="主导航">
        <RouterLink to="/findbook" class="nav-link">找书</RouterLink>
        <RouterLink to="/knowledge" class="nav-link">知识地图</RouterLink>
        <RouterLink to="/seat" class="nav-link">座位预测</RouterLink>
      </nav>
    </div>
    <!-- 任何请求进行中: 顶部细线「翻阅中」 -->
    <div class="progress-line" :class="{ active: pendingRequests > 0 }" aria-hidden="true"></div>
  </header>

  <main class="site-main">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </main>

  <footer class="site-foot">© 2026 大连理工大学图书馆</footer>
</template>

<style scoped>
.site-head {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  height: var(--nav-h);
  background: var(--color-paper);
  border-bottom: 1px solid var(--color-line);
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

.nav {
  display: flex;
  align-items: center;
  gap: 1.75rem;
  flex-shrink: 0;
}

.nav-link {
  position: relative;
  padding: 0.3rem 0;
  color: var(--color-ink-soft);
  font-size: 15px;
  white-space: nowrap;
  text-decoration: none;
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
  transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
}

.nav-link:hover {
  color: var(--color-ink);
}

.nav-link:hover::after,
.nav-link.router-link-active::after {
  transform: scaleX(1);
}

.nav-link.router-link-active {
  color: var(--color-teal);
  font-weight: 500;
}

.site-main {
  max-width: var(--measure);
  margin: 0 auto;
  padding: calc(var(--nav-h) + 2.5rem) 1.5rem 4rem;
  min-height: calc(100vh - 120px);
}

.site-foot {
  padding: 1.5rem;
  text-align: center;
  border-top: 1px solid var(--color-line);
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
  background: var(--color-paper);
}

.splash-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 1.75rem 2.25rem;
  background: var(--color-card);
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
  animation: page-progress 1.4s cubic-bezier(0.22, 1, 0.36, 1) infinite;
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

@media (max-width: 640px) {
  .brand-sub {
    display: none;
  }
  .head-inner {
    padding: 0 1rem;
  }
  .nav {
    gap: 1.1rem;
  }
}
</style>
