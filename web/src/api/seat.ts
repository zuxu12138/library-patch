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

export async function sendFeedback(feedback: string): Promise<string[]> {
  const result = await unwrap<{ memory_ids: string[] }>(http.post("/seat/feedback", { feedback }));
  return result.memory_ids;
}
