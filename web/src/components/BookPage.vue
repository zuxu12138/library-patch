<script setup lang="ts">
/** 一张纸: 正面是章节内容, 背面是镜像的眉线+页码(翻起时露出)。
    光影全部由 .book 上的 --turn 变量驱动, 本组件不含任何逐帧 JS。
    turning=true(正在翻动的页)才启用掀侧/纸背光影——
    否则翻页进度值会残留在落定页面上, 把纸面染灰。 */
import { TOTAL_NUMERAL, type Chapter } from "../book/book";

defineProps<{ chapter: Chapter; turning?: boolean }>();
</script>

<template>
  <div class="bookpage" :class="{ turning }">
    <!-- 正面 -->
    <div class="face front">
      <header class="eyebrow">
        <span class="eyebrow-label">CHAPTER {{ chapter.no }} · {{ chapter.cn }}</span>
        <span class="eyebrow-rule" aria-hidden="true"></span>
        <span class="eyebrow-en">{{ chapter.en }}</span>
      </header>

      <div class="paper-body">
        <slot />
      </div>

      <footer class="folio" aria-hidden="true">{{ chapter.numeral }} / {{ TOTAL_NUMERAL }}</footer>

      <!-- 装订线内凹阴影(常驻) + 翻起侧受光变化(随 --turn 加深) -->
      <i class="spine-shade" aria-hidden="true"></i>
      <i class="lift-shade" aria-hidden="true"></i>
    </div>

    <!-- 背面: 镜像印刷, 透明度 0.15 -->
    <div class="face back" aria-hidden="true">
      <div class="mirror">
        <span class="m-eyebrow">CHAPTER {{ chapter.no }} · {{ chapter.cn }}</span>
        <span class="m-numeral">{{ chapter.numeral }}</span>
        <span class="m-rule"></span>
        <span class="m-folio">{{ chapter.numeral }} / {{ TOTAL_NUMERAL }}</span>
      </div>
      <i class="back-shade"></i>
    </div>
  </div>
</template>

<style scoped>
.bookpage {
  height: 100%;
}

.face {
  background: var(--color-paper);
  background-image: var(--paper-noise);
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}

/* 正面: under 页在文档流里撑起书高; 翻动的页由 BookShell 改为 absolute 裁切 */
.face.front {
  position: relative;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  padding: 1.1rem 2rem 2.5rem;
  box-sizing: border-box;
}

/* 背面 */
.face.back {
  position: absolute;
  inset: 0;
  transform: rotateY(180deg);
  overflow: hidden;
}

/* 章节眉线: 细线 + 等宽小字 */
.eyebrow {
  display: flex;
  align-items: baseline;
  gap: 0.9rem;
  padding-bottom: 0.7rem;
  margin-bottom: 1.75rem;
  border-bottom: 1px solid var(--color-line);
}

.eyebrow-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink-muted);
  white-space: nowrap;
}

.eyebrow-rule {
  flex: 1;
  height: 1px;
  background: var(--color-line);
  transform: translateY(-3px);
}

.eyebrow-en {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  color: var(--color-teal);
  white-space: nowrap;
}

.paper-body {
  flex: 1;
  min-width: 0;
}

/* 页码: 衬线体, 右下角 */
.folio {
  position: absolute;
  right: 2rem;
  bottom: 0.9rem;
  font-family: var(--font-serif);
  font-size: 12.5px;
  color: var(--color-ink-muted);
  letter-spacing: 0.1em;
}

/* 书脊: 左侧 20px 极淡内凹阴影, 暗示装订厚度 */
.spine-shade {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 20px;
  pointer-events: none;
  background: linear-gradient(to right, rgba(28, 28, 26, 0.06), rgba(28, 28, 26, 0.015) 55%, transparent);
}

/* 翻起侧光影: 角度越大, 掀起的右缘越暗, 纸面受光越不均匀。
   仅 .turning(正在翻动的页)启用, 落定页保持干净纸面 */
.lift-shade,
.back-shade {
  opacity: 0;
}

.turning .lift-shade,
.turning .back-shade {
  opacity: 1;
}

.lift-shade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    to left,
    rgba(28, 28, 26, calc(var(--turn, 0) * 0.32)) 0%,
    rgba(28, 28, 26, calc(var(--turn, 0) * 0.07)) 42%,
    transparent 68%
  );
}

/* 纸背受光: 翻过 90° 后, 越接近落页越亮 */
.back-shade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
    to right,
    rgba(28, 28, 26, calc((1 - var(--turn, 1)) * 0.24)) 0%,
    rgba(28, 28, 26, calc((1 - var(--turn, 1)) * 0.05)) 45%,
    transparent 70%
  );
}

/* 背面镜像印刷: 淡淡透出的上一页 */
.mirror {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  padding: 1.1rem 2rem 2.5rem;
  transform: scaleX(-1);
  opacity: 0.15;
}

.m-eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-ink);
  padding-bottom: 0.7rem;
  border-bottom: 1px solid var(--color-ink);
}

.m-numeral {
  flex: 1;
  display: grid;
  place-items: center;
  font-family: var(--font-serif);
  font-size: 7rem;
  font-weight: 600;
  color: var(--color-ink);
}

.m-rule {
  height: 1px;
  background: var(--color-ink);
  margin-bottom: 0.9rem;
}

.m-folio {
  align-self: flex-end;
  font-family: var(--font-serif);
  font-size: 12.5px;
  letter-spacing: 0.1em;
  color: var(--color-ink);
}

@media (max-width: 640px) {
  .face.front {
    padding: 0.9rem 1.1rem 2.4rem;
  }
  .folio {
    right: 1.1rem;
  }
  .eyebrow-en {
    display: none;
  }
}
</style>
