import { http, unwrap } from "./client";

export interface GraphNode {
  paperId: string;
  title?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface CitationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export async function buildGraph(paperId: string): Promise<CitationGraph> {
  return unwrap(http.post("/knowledge/graph", { paper_id: paperId }));
}

export async function summarizePaper(paperId: string): Promise<Record<string, unknown>> {
  return unwrap(http.post("/knowledge/summarize", { paper_id: paperId }));
}
