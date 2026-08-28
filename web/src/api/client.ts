import axios, { type AxiosInstance } from "axios";

export interface Envelope<T> {
  code: number;
  msg: string;
  data: T | null;
}

const USER_ID_KEY = "library-patch-user-id";

function getUserId(): string {
  const existing = localStorage.getItem(USER_ID_KEY);
  if (existing) return existing;
  localStorage.setItem(USER_ID_KEY, "default");
  return "default";
}

export const http: AxiosInstance = axios.create({
  baseURL: (import.meta as any).env?.VITE_AGENT_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 10000,
});

http.interceptors.request.use((request) => {
  request.headers["X-User-Id"] = getUserId();
  return request;
});

const ERROR_MESSAGES: Record<number, string> = {
  50001: "图书馆数据服务暂时不可用，请稍后再试",
  50002: "图书馆数据服务暂时不可用，请稍后再试",
  60001: "AI 助手暂时无法使用，已为你展示基础结果",
  60002: "偏好记忆服务异常，本次结果可能未个性化",
};

export function mapErrorMessage(code: number): string {
  if (code === 0) return "";
  return ERROR_MESSAGES[code] ?? "出了点问题，请稍后再试";
}

export async function unwrap<T>(promise: Promise<{ data: Envelope<T> }>): Promise<T> {
  const response = await promise;
  const env = response.data;
  if (env.code !== 0) {
    throw new Error(mapErrorMessage(env.code));
  }
  return env.data as T;
}
