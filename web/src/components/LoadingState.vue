<script setup lang="ts">
</script>

<template>
  <div class="loading-state" role="status" aria-live="polite">
    <span class="spinner" aria-hidden="true"></span>
    <span>加载中…</span>
  </div>
</template>

<style scoped>
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.65rem;
  padding: 2.5rem 0;
  color: var(--ink-soft);
  font-size: var(--fs-body);
}

.spinner {
  width: 1.3rem;
  height: 1.3rem;
  border-radius: 50%;
  border: 2.5px solid var(--dut-blue-light);
  border-top-color: var(--dut-blue);
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
    border-top-color: var(--dut-blue);
  }
}
</style>
