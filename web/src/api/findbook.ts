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
}

export async function searchBooks(query: string, page = 1, pageSize = 10): Promise<FindBookResult> {
  return unwrap(http.post("/findbook/search", { query, page, page_size: pageSize }));
}

export async function sendFeedback(feedback: string): Promise<string[]> {
  const result = await unwrap<{ memory_ids: string[] }>(http.post("/findbook/feedback", { feedback }));
  return result.memory_ids;
}
