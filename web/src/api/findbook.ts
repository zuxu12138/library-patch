import { http, unwrap } from "./client";

export interface Holding {
  callNo: string;
  location: string;
  status: string;
  available: boolean;
  barCode: string;
}

export interface Book {
  bibId: string;
  title: string;
  author: string;
  publisher: string;
  pubYear: string;
  isbn: string;
  classNo: string;
  callNos: string[];
  abstract: string;
  holdings: Holding[];
}

export interface FindBookResult {
  total: number;
  page: number;
  pageSize: number;
  books: Book[];
  plan_note?: string; // 记忆生效时的偏好说明, 如"已按你的偏好只找近五年"
}

export async function searchBooks(query: string, page = 1, pageSize = 10): Promise<FindBookResult> {
  return unwrap(http.post("/findbook/search", { query, page, page_size: pageSize }));
}

export interface FeedbackResult {
  memory_ids: string[];
  llm_available: boolean; // false 时反馈没有沉淀成记忆(未配置模型)
}

export async function sendFeedback(feedback: string): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(http.post("/findbook/feedback", { feedback }));
}
