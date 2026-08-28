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
    submittedHint.value =
      result && result.llm_available === false
        ? "已收到，但偏好记忆未启用（未配置模型），本次不会被记住"
        : "已记录，谢谢反馈";
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
    <Transition name="panel">
      <div v-if="open" class="panel" role="dialog" aria-label="意见反馈">
        <div class="panel-head">
          <span>意见反馈</span>
          <button type="button" class="close" aria-label="关闭" @click="emit('toggle')">×</button>
        </div>
        <p class="panel-tip">这条结果准确吗？</p>
        <div class="thumbs">
          <button type="button" class="thumb" :disabled="submitting" @click="submit('赞:')">👍 准确</button>
          <button type="button" class="thumb" :disabled="submitting" @click="submit('差评:')">👎 不准确</button>
        </div>
        <textarea
          v-model="text"
          placeholder="补充说明（可选）"
          rows="3"
          aria-label="补充说明"
        ></textarea>
        <button type="button" class="submit" :disabled="submitting" @click="submit('')">
          提交反馈
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
      <span aria-hidden="true">💬</span>
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

.fab {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  background: var(--dut-blue);
  color: #fff;
  font-size: 24px;
  box-shadow: 0 6px 20px rgba(0, 61, 165, 0.35);
  transition: transform 0.2s ease, background 0.2s ease;
}

.fab:hover {
  background: var(--dut-blue-bright);
  transform: translateY(-2px);
}

.panel {
  width: 300px;
  max-width: calc(100vw - 2rem);
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: 0 12px 40px rgba(0, 61, 165, 0.18);
  padding: 1rem 1.1rem;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--ink-muted);
  padding: 0.1rem 0.3rem;
}

.panel-tip {
  margin: 0.5rem 0 0.5rem;
  font-size: 13px;
  color: var(--ink-soft);
}

.thumbs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.thumb {
  flex: 1;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--bg);
  font-size: 13px;
  color: var(--ink);
  transition: border-color 0.15s ease;
}

.thumb:hover:not(:disabled) {
  border-color: var(--dut-blue);
}

textarea {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  resize: vertical;
  font-size: 14px;
}

textarea:focus {
  outline: none;
  border-color: var(--dut-blue);
  box-shadow: 0 0 0 3px rgba(0, 61, 165, 0.1);
}

.submit {
  width: 100%;
  margin-top: 0.6rem;
  padding: 0.45rem;
  border: none;
  border-radius: 8px;
  background: var(--dut-blue);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s ease;
}

.submit:hover:not(:disabled) {
  background: var(--dut-blue-bright);
}

.submit:disabled,
.thumb:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ok {
  margin: 0.5rem 0 0;
  color: var(--available);
  font-size: 13px;
}

.err {
  margin: 0.5rem 0 0;
  color: var(--dut-red);
  font-size: 13px;
}

.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}
</style>
