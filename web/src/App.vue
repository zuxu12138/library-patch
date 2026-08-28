<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <header class="site-head">
    <div class="head-inner">
      <div class="brand">
        <span class="brand-accent" aria-hidden="true"></span>
        <span class="brand-name">
          <strong>大连理工大学</strong>
          <span class="brand-sep">·</span>
          <span>图书馆智慧服务</span>
        </span>
      </div>

      <nav class="nav" aria-label="主导航">
        <RouterLink to="/findbook" class="nav-link">找书</RouterLink>
        <RouterLink to="/knowledge" class="nav-link">知识地图</RouterLink>
        <RouterLink to="/seat" class="nav-link">座位预测</RouterLink>
      </nav>
    </div>
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
  background: linear-gradient(
    135deg,
    rgba(0, 61, 165, 0.94),
    rgba(0, 82, 204, 0.94)
  );
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset;
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
  gap: 0.6rem;
  min-width: 0;
}

.brand-accent {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--dut-red);
}

.brand-name {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  color: #fff;
  white-space: nowrap;
}

.brand-name strong {
  font-size: 17px;
  font-weight: 700;
}

.brand-sep {
  color: rgba(255, 255, 255, 0.6);
}

.brand-name > span:last-child {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.nav {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.nav-link {
  position: relative;
  padding: 0.4rem 0.85rem;
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.nav-link::after {
  content: "";
  position: absolute;
  left: 0.85rem;
  right: 0.85rem;
  bottom: 0;
  height: 2px;
  border-radius: 1px;
  background: #fff;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.22s ease;
}

.nav-link:hover {
  color: #fff;
}

.nav-link:hover::after,
.nav-link.router-link-active::after {
  transform: scaleX(1);
}

.nav-link.router-link-active {
  color: #fff;
}

.site-main {
  max-width: var(--measure);
  margin: 0 auto;
  padding: calc(var(--nav-h) + 2rem) 1.5rem 3.5rem;
}

.site-foot {
  padding: 1.25rem 1.5rem 2.5rem;
  text-align: center;
  background: var(--card);
  border-top: 1px solid var(--line);
  color: var(--ink-muted);
  font-size: 13px;
}

/* 页面切换 fade-in */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .brand-name > span:last-child {
    display: none;
  }
  .brand-sep {
    display: none;
  }
  .head-inner {
    padding: 0 1rem;
  }
  .nav-link {
    padding: 0.4rem 0.6rem;
  }
}
</style>
