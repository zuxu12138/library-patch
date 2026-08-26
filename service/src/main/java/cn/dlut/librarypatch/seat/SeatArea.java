package cn.dlut.librarypatch.seat;

/**
 * 一个座位区域的实时占用（来自 360banke/晓图座位系统）。字段对齐 docs/接口契约.md 契约①。
 *
 * @param mapId    楼层/地图 ID
 * @param areaName 区域名, 如 "201文艺期刊阅览室"
 * @param libCode  馆代码, 如 "lingxi" / "bochuan" / "panjin"
 * @param total    座位总数
 * @param free     空闲座位数
 * @param occupied 已占用座位数
 */
public record SeatArea(
        String mapId,
        String areaName,
        String libCode,
        int total,
        int free,
        int occupied
) {}
