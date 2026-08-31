import { http, unwrap } from "./client";

export interface SeatRankingItem {
  preference_score?: number;
  preference_reason?: string;
  area_name: string;
  avg_occupancy_rate: number;
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
  is_open: boolean;              // 所选时段是否在开馆时间(07:00–22:00)内
  open_hours: number[];          // [开馆小时, 闭馆小时), 如 [7, 22]
  fetched_at: string | null;     // 实时数据拉取时刻 "HH:MM"; 闭馆/降级时为 null
}

export interface SeatItem {
  seatId: string;
  seatNum: string;
  x: number;
  y: number;
  busy: boolean;
  seatType: string;
  status: string;   // 预约状态原文: 可预约 / 已预约 / 不可预约(闭馆) 等
}

export interface SeatMap {
  mapId: string;
  count: number;
  seats: SeatItem[];
  is_open?: boolean;
  fetched_at?: string;      // 拉取时刻 "HH:MM"
  open_hours?: number[];    // [开馆小时, 闭馆小时)
}

export async function predictSeats(weekday: number, hour: number): Promise<SeatPrediction> {
  return unwrap(http.post("/seat/predict", { weekday, hour }));
}

export async function fetchSeatMap(mapId: string): Promise<SeatMap> {
  return unwrap(http.post("/seat/map", { map_id: mapId }));
}

import type { FeedbackResult } from "./findbook";

export async function sendFeedback(feedback: string): Promise<FeedbackResult> {
  return unwrap<FeedbackResult>(http.post("/seat/feedback", { feedback }));
}
