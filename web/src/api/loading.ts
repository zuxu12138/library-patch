import { ref } from "vue";

/** 全局请求进行中计数: >0 时 App 顶部显示「翻阅中」细线 */
export const pendingRequests = ref(0);

export function beginRequest() {
  pendingRequests.value++;
}

export function endRequest() {
  pendingRequests.value = Math.max(0, pendingRequests.value - 1);
}
