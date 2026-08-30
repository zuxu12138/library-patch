<script setup lang="ts">
/** 印章体系
 *  - seal: 方形白文朱砂钤印（白字红底），边缘做 5%~10% 洇墨残缺，随机微倾
 *  - idle: 淡墨闲章（朱文细框），用于空态
 */
import { onMounted, ref } from "vue";

const props = defineProps<{
  variant: "seal" | "idle";
  text: string;
  subtext?: string;
  size?: "sm" | "md";
}>();

const rotate = ref(0);
const clipId = ref("");

onMounted(() => {
  // 随机微倾：-12° ~ 12°，印章从来不是正的
  rotate.value = Math.round((Math.random() * 24 - 12) * 10) / 10;
  clipId.value = `seal-clip-${Math.random().toString(36).slice(2, 9)}`;
});

const sizeClass = props.size === "sm" ? "seal-sm" : "seal-md";
</script>

<template>
  <span class="seal-stamp" :class="[variant, sizeClass]" :style="{ '--seal-rotate': `${rotate}deg` }">
    <svg v-if="variant === 'seal'" class="seal-edge" viewBox="0 0 80 80" aria-hidden="true">
      <defs>
        <clipPath :id="clipId">
          <polygon
            points="2,6 8,2 74,2 78,8 78,72 72,78 8,78 2,72"
            stroke="none"
            fill="currentColor"
          />
        </clipPath>
      </defs>
      <rect
        x="0"
        y="0"
        width="80"
        height="80"
        :clip-path="`url(#${clipId})`"
        fill="currentColor"
      />
      <!-- 洇墨残缺: 边缘随机咬掉的小缺口 -->
      <circle cx="6" cy="4" r="2.2" fill="var(--color-paper)" />
      <circle cx="74" cy="7" r="1.8" fill="var(--color-paper)" />
      <circle cx="78" cy="68" r="2.5" fill="var(--color-paper)" />
      <circle cx="5" cy="74" r="1.6" fill="var(--color-paper)" />
      <circle cx="40" cy="1.5" r="1.2" fill="var(--color-paper)" />
      <circle cx="40" cy="78.5" r="1.4" fill="var(--color-paper)" />
    </svg>

    <span class="seal-text">
      <span class="seal-main">{{ text }}</span>
      <span v-if="subtext" class="seal-sub">{{ subtext }}</span>
    </span>
  </span>
</template>

<style scoped>
.seal-stamp {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
  transform: rotate(var(--seal-rotate, 0deg));
  animation: stamp 0.15s var(--ease-out) both;
}

@keyframes stamp {
  from {
    opacity: 0;
    transform: rotate(var(--seal-rotate, 0deg)) scale(1.25);
  }
  to {
    opacity: 1;
    transform: rotate(var(--seal-rotate, 0deg)) scale(1);
  }
}

/* 方形白文朱砂钤印 */
.seal-stamp.seal {
  color: var(--color-seal);
  background: var(--color-seal);
}

.seal-stamp.seal-md {
  width: 58px;
  height: 58px;
}

.seal-stamp.seal-sm {
  width: 44px;
  height: 44px;
}

.seal-edge {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  color: var(--color-seal);
  pointer-events: none;
}

.seal-text {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-paper);
  line-height: 1;
}

.seal-main {
  font-family: var(--font-serif);
  font-weight: 600;
  letter-spacing: 0.06em;
}

.seal-md .seal-main {
  font-size: 14px;
}

.seal-sm .seal-main {
  font-size: 11px;
}

.seal-sub {
  font-size: 8px;
  letter-spacing: 0.04em;
  margin-top: 2px;
  opacity: 0.9;
}

/* 淡墨闲章 */
.seal-stamp.idle {
  color: var(--color-ink-muted);
  border: 1px solid var(--color-ink-muted);
  background: transparent;
  padding: 0.35rem 0.65rem;
  min-height: 44px;
}

.seal-stamp.idle .seal-main {
  color: var(--color-ink-muted);
  font-family: var(--font-serif);
  font-size: 15px;
}

@media (prefers-reduced-motion: reduce) {
  .seal-stamp {
    animation: none;
  }
}
</style>
