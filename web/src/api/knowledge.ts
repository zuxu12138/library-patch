import { http, unwrap } from "./client";

export interface GraphNode {
  paperId: string;
  title?: string;
  year?: number;
  citationCount?: number;
  depth?: 0 | 1 | 2;
}

export interface GraphEdge {
  source: string;
  target: string;
  depth?: 1 | 2;
}

export interface CitationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  maxDepth?: number;
  error?: string; // S2 限流降级时存在
}

export async function buildGraph(paperId: string): Promise<CitationGraph> {
  return unwrap(http.post("/knowledge/graph", { paper_id: paperId }, { timeout: 60000 }));
}

export interface PaperAuthor {
  name: string;
}

export interface OpenAccessPdf {
  url: string;
  license?: string;
}

export interface PaperSummary {
  paperId?: string;
  title?: string;
  year?: number;
  citationCount?: number;
  abstract?: string;
  authors?: PaperAuthor[];
  openAccessPdf?: OpenAccessPdf | null;
  error?: string; // S2 限流降级时存在
}

export async function summarizePaper(paperId: string): Promise<PaperSummary> {
  return unwrap(http.post("/knowledge/summarize", { paper_id: paperId }));
}

export interface PaperSearchResult {
  papers: GraphNode[];
  error?: string;
}

export async function searchPapers(query: string): Promise<PaperSearchResult> {
  return unwrap(http.post("/knowledge/search", { query }));
}
