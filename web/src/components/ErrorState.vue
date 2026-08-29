<script setup lang="ts">
// 业务错误/网络异常展示: 图书馆语境文案由 api/client.ts 的错误码映射给出
defineProps<{ message: string }>();
</script>

<template>
  <div class="error-state" role="alert">
    <span class="rule" aria-hidden="true"></span>
    <div class="text">
      <strong>暂时取不到</strong>
      <p>{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  gap: 0.9rem;
  align-items: flex-start;
  max-width: 560px;
  margin: 0 auto;
  padding: 1rem 1.25rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
}

.rule {
  flex-shrink: 0;
  width: 3px;
  align-self: stretch;
  background: var(--color-seal);
}

.text {
  min-width: 0;
}

.text strong {
  display: block;
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 600;
}

.text p {
  margin: 0.2rem 0 0;
  font-size: 14px;
  color: var(--color-ink-soft);
  line-height: 1.6;
}
</style>
