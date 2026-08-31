import { http, unwrap } from "./client";

export interface SeatRankingItem {
  preference_score?: number;
  preference_reason?: string;
  area_name: string;
  avg_occupancy_rate: number | null;
  sample_days?: number;
  predicted_available?: number | null;
  occupied_now?: number | null;
  unavailable_now?: number | null;
  unknown_now?: number | null;
  updated_at?: string;
  fresh?: boolean;
  recommendable?: boolean;
  samples: number;          // 历史采样点数, <4 时提示置信度低
  free_now: number | null;  // 实时空闲; realtime_available=false 时为 null, 不得渲染假数据
  total: number | null;
  map_id: string | null;    // 楼层 id, 用于下钻座位平面图
  lib_code: string | null;  // 馆代码 bochuan/lingxi/panjin/kaifaqu
}

export interface SeatPrediction {
  personalization?: { applied: boolean; note: string; memory_ids: string[] };
  ranking: SeatRankingItem[];
  realtime_available: boolean;
  mode?: "now" | "plan";
  closed?: boolean;
  message?: string;
}

export interface SeatItem {
  seatId: string;
  seatNum: string;
  x: number;
  y: number;
  busy: boolean;
  seatType: string;
  status: string;
}

export interface SeatMap {
  mapId: string;
  count: number;
  seats: SeatItem[];
}

export async function predictSeats(weekday: number, hour: number, mode: "now" | "plan" = "now"): Promise<SeatPrediction> {
  return unwrap(http.post("/seat/predict", { weekday, hour, mode }));
}

export async function fetchSeatMap(mapId: string): Promise<SeatMap> {
  return unwrap(http.post("/seat/map", { map_id: mapId }));
}

import type { FeedbackResult } from "./findbook";

export async function sendFeedback(feedback: string): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(http.post("/seat/feedback", { feedback }));
}
