<script setup lang="ts">
defineProps<{ message: string }>();
</script>

<template>
  <div class="error-state" role="alert">
    <span class="icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
        <line x1="12" y1="8" x2="12" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        <circle cx="12" cy="16.5" r="1.2" fill="currentColor" />
      </svg>
    </span>
    <div class="text">
      <strong>没有取到结果</strong>
      <p>{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  max-width: 600px;
  margin: 0 auto;
  padding: 1rem 1.15rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 4px solid var(--dut-red);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}

.icon {
  flex-shrink: 0;
  color: var(--dut-red);
  margin-top: 0.1rem;
}

.text {
  min-width: 0;
}

.text strong {
  display: block;
  font-size: 15px;
}

.text p {
  margin: 0.15rem 0 0;
  font-size: 14px;
  color: var(--ink-soft);
}
</style>
