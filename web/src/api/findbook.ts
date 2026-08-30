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
  abstractText: string; // 后端 Book.java 序列化字段；保留对旧字段 abstract 的运行时兼容
  holdings: Holding[];
}

export interface FindBookResult {
  total: number;
  page: number;
  pageSize: number;
  books: Book[];
  plan_note?: string; // 记忆生效时的偏好说明
  error?: string; // OPAC 故障且 code=0 时的降级错误文案
}

export async function searchBooks(query: string, page = 1, pageSize = 10): Promise<FindBookResult> {
  const raw = await unwrap<FindBookResult>(http.post("/findbook/search", { query, page, page_size: pageSize }));
  // 后端在 OPAC 故障时可能以 code=0 返回 {error, plan_note}，前端把它当成业务错误抛出
  if (raw.error) {
    throw new Error(raw.error);
  }
  // 兼容旧字段 abstract，优先取 abstractText
  const books = (raw.books ?? []).map((b) => ({
    ...b,
    abstractText: (b as unknown as Record<string, string>).abstractText ?? (b as unknown as Record<string, string>).abstract ?? "",
  }));
  return {
    total: raw.total ?? 0,
    page: raw.page ?? page,
    pageSize: raw.pageSize ?? pageSize,
    books,
    plan_note: raw.plan_note,
  };
}

export interface FeedbackResult {
  memory_ids: string[];
  llm_available: boolean; // false 时反馈没有沉淀成记忆(未配置模型)
}

export async function sendFeedback(feedback: string): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(http.post("/findbook/feedback", { feedback }));
}
