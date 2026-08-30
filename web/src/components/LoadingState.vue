<script setup lang="ts">
// 骨架屏呼吸动画, 禁用旋转 loading(设计规格)
defineProps<{ rows?: number }>();
</script>

<template>
  <div class="loading-state" role="status" aria-live="polite" aria-label="加载中">
    <div
      v-for="i in rows ?? 3"
      :key="i"
      class="skeleton skeleton-row"
      :style="{ width: i % 3 === 0 ? '62%' : i % 3 === 2 ? '84%' : '76%', animationDelay: `${(i - 1) * 120}ms` }"
    ></div>
  </div>
</template>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1.5rem 0;
}

.skeleton-row {
  height: 18px;
}
</style>
