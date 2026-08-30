package cn.dlut.librarypatch.web;

import cn.dlut.librarypatch.common.ApiResponse;
import cn.dlut.librarypatch.seat.SeatArea;
import cn.dlut.librarypatch.seat.SeatClient;
import cn.dlut.librarypatch.seat.SeatException;
import cn.dlut.librarypatch.seat.SeatItem;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 座位实时占用 API（契约①）。给"现在"的各区域占用；
 * 历史序列由采集器攒、P2 预测读采集库，二者互补。
 * 响应统一走 {code,msg,data} 信封；trace_id 由 TraceFilter 自动处理。
 */
@RestController
public class SeatController {

    private final SeatClient seatClient;

    public SeatController(SeatClient seatClient) {
        this.seatClient = seatClient;
    }

    /** GET /api/seats/now */
    @GetMapping("/api/seats/now")
    public ApiResponse<Map<String, Object>> now() {
        try {
            List<SeatArea> areas = seatClient.areaOccupancy();
            return ApiResponse.ok(Map.of("count", areas.size(), "areas", areas));
        } catch (SeatException e) {
            return ApiResponse.error(ApiResponse.ERR_SEAT_UNREACHABLE, "座位系统暂不可达，请稍后再试");
        }
    }

    /** GET /api/seats/map?mapid=2498 — 单座级实时平面图。
     *  空数据(该楼层暂无数据)不是故障: 返回 code=0 + 空列表,
     *  50002 只留给真正的通信/解析故障——调用方据此区分"没数据"和"系统挂了"。 */
    @GetMapping("/api/seats/map")
    public ApiResponse<Map<String, Object>> map(@RequestParam("mapid") String mapId) {
        try {
            List<SeatItem> seats = seatClient.seatMap(mapId);
            return ApiResponse.ok(Map.of("mapId", mapId, "count", seats.size(), "seats", seats));
        } catch (SeatException e) {
            return ApiResponse.error(ApiResponse.ERR_SEAT_UNREACHABLE, "座位系统暂不可达，请稍后再试");
        }
    }
}
