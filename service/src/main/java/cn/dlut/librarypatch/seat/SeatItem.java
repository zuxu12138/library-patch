package cn.dlut.librarypatch.seat;

/**
 * 单个座位的实时状态（来自 GetSeatList.asp）。mappos 是楼层平面图坐标(像素)。
 *
 * @param seatId   座位 UUID
 * @param seatNum  座位号, 如 "001"
 * @param x        平面图 x 坐标
 * @param y        平面图 y 坐标
 * @param busy     当前是否被占用
 * @param seatType 设施标记, 如 "电源|台灯"
 * @param status   预约状态原文, 如 "不可预约"
 */
public record SeatItem(
        String seatId,
        String seatNum,
        int x,
        int y,
        boolean busy,
        String seatType,
        String status
) {}
