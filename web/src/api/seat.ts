import { http, unwrap } from "./client";

export interface SeatRankingItem {
  area_name: string;
  avg_occupancy_rate: number;
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
