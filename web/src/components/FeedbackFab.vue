<script setup lang="ts">
import { ref, watch } from "vue";

const props = defineProps<{
  open: boolean;
  onSubmit: (text: string) => Promise<{ llm_available?: boolean } | void>;
}>();
const emit = defineEmits<{ (e: "toggle"): void }>();

const text = ref("");
const submitted = ref(false);
const submittedHint = ref("已记录，谢谢反馈");
const submitting = ref(false);
const errorMessage = ref("");

watch(
  () => props.open,
  (v) => {
    if (!v) {
      submitted.value = false;
      errorMessage.value = "";
    }
  }
);

async function submit(prefix: string) {
  const feedbackText = prefix ? `${prefix}${text.value}` : text.value;
  if (!feedbackText.trim()) return;
  submitting.value = true;
  errorMessage.value = "";
  try {
    const result = await props.onSubmit(feedbackText);
    // 诚实提示: 未配置模型时明确告知不会被记住
    submittedHint.value =
      result && result.llm_available === false
        ? "已收到，但偏好记忆未启用（未配置模型），本次不会被记住"
        : "已记住，下次检索会按你的偏好调整";
    submitted.value = true;
    text.value = "";
    window.setTimeout(() => {
      submitted.value = false;
    }, 2500);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "反馈提交失败，请稍后再试";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="feedback-fab">
    <Transition name="note">
      <div v-if="open" class="panel" role="dialog" aria-label="意见反馈">
        <div class="tear-line" aria-hidden="true"></div>
        <div class="panel-head">
          <span class="panel-title">批注</span>
          <button type="button" class="close" aria-label="关闭" @click="emit('toggle')">×</button>
        </div>
        <p class="panel-tip">这条结果准确吗？你的反馈会成为下次检索的偏好。</p>
        <div class="thumbs">
          <button type="button" class="thumb" :disabled="submitting" @click="submit('赞:')">准确</button>
          <button type="button" class="thumb" :disabled="submitting" @click="submit('差评:')">不准确</button>
        </div>
        <textarea
          v-model="text"
          placeholder="补充说明（可选）"
          rows="3"
          aria-label="补充说明"
        ></textarea>
        <button type="button" class="submit" :disabled="submitting" @click="submit('')">
          提交批注
        </button>
        <p v-if="submitted" class="ok" role="status">{{ submittedHint }}</p>
        <p v-if="errorMessage" class="err" role="alert">{{ errorMessage }}</p>
      </div>
    </Transition>

    <button
      type="button"
      class="fab"
      :class="{ active: open }"
      :aria-expanded="open"
      aria-label="意见反馈"
      @click="emit('toggle')"
    >
      <svg viewBox="0 0 24 24" fill="none" width="20" height="20" aria-hidden="true">
        <path
          d="M4 20l1.2-4.2L16.5 4.5a2.1 2.1 0 0 1 3 3L8.2 18.8 4 20z"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.feedback-fab {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.75rem;
}

/* 悬浮墨点: 纯色圆点 */
.fab {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: var(--color-teal);
  color: #fff;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.fab:hover {
  background: var(--color-teal-deep);
  transform: translateY(-2px);
}

/* 便签纸面板 */
.panel {
  position: relative;
  width: 300px;
  max-width: calc(100vw - 2rem);
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 1.25rem 1.25rem 1.1rem;
}

/* 撕边虚线 */
.tear-line {
  position: absolute;
  top: 0.55rem;
  left: 0.75rem;
  right: 0.75rem;
  border-top: 1px dashed var(--color-line);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.35rem;
}

.panel-title {
  font-family: var(--font-serif);
  font-weight: 600;
  font-size: 15px;
}

.close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--color-ink-muted);
  padding: 0.1rem 0.3rem;
  cursor: pointer;
}

.panel-tip {
  margin: 0.5rem 0 0.6rem;
  font-size: 13px;
  color: var(--color-ink-soft);
  line-height: 1.6;
}

.thumbs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.thumb {
  flex: 1;
  min-height: 44px;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  background: var(--color-paper);
  font-size: 13px;
  color: var(--color-ink);
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.thumb:hover:not(:disabled) {
  border-color: var(--color-teal);
}

textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  background: var(--color-card);
  resize: vertical;
  font-size: 14px;
  font-family: var(--font-sans);
}

textarea:focus {
  outline: none;
  border-color: var(--color-teal);
}

.submit {
  width: 100%;
  min-height: 44px;
  margin-top: 0.6rem;
  padding: 0.45rem;
  border: none;
  border-radius: 2px;
  background: var(--color-teal);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: background 0.15s ease;
}

.submit:hover:not(:disabled) {
  background: var(--color-teal-deep);
}

.submit:disabled,
.thumb:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ok {
  margin: 0.5rem 0 0;
  color: var(--color-available);
  font-size: 13px;
  line-height: 1.5;
}

.err {
  margin: 0.5rem 0 0;
  color: var(--color-seal);
  font-size: 13px;
}

/* 便签纸: 关闭时向内对折收起 */
.note-enter-active,
.note-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
  transform-origin: bottom;
}

.note-enter-from,
.note-leave-to {
  opacity: 0;
  transform: scaleY(0);
}
</style>
