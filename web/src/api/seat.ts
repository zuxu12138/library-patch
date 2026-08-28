import { http, unwrap } from "./client";

export interface SeatRankingItem {
  area_name: string;
  avg_occupancy_rate: number;
  samples: number;          // 历史采样点数, <4 时提示置信度低
  free_now: number | null;  // 实时空闲; realtime_available=false 时为 null, 不得渲染假数据
  total: number | null;
}

export interface SeatPrediction {
  ranking: SeatRankingItem[];
  realtime_available: boolean;
}

export async function predictSeats(weekday: number, hour: number): Promise<SeatPrediction> {
  return unwrap(http.post("/seat/predict", { weekday, hour }));
}

import type { FeedbackResult } from "./findbook";

export async function sendFeedback(feedback: string): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(http.post("/seat/feedback", { feedback }));
}
