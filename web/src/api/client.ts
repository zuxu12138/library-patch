import axios, { type AxiosInstance } from "axios";
import { beginRequest, endRequest } from "./loading";

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
  beginRequest();
  return request;
});

// 任何请求结束(成功/失败)都归还计数, 驱动顶部进度细线
http.interceptors.response.use(
  (response) => {
    endRequest();
    return response;
  },
  (error) => {
    endRequest();
    return Promise.reject(error);
  }
);

// 错误码 → 图书馆语境文案(设计规格强制映射, 禁止展示技术性报错原文)
const ERROR_MESSAGES: Record<number, string> = {
  40001: "书脊上的标签模糊不清，请重新输入关键词",
  50001: "书架暂时清点中，请稍后再来",
  50002: "书架暂时清点中，请稍后再来",
  60001: "图书馆员正在整理档案，服务暂未开启",
  60002: "图书馆员正在整理档案，服务暂未开启",
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
