package cn.dlut.librarypatch.web;

import cn.dlut.librarypatch.common.ApiResponse;
import cn.dlut.librarypatch.seat.SeatArea;
import cn.dlut.librarypatch.seat.SeatClient;
import org.springframework.web.bind.annotation.GetMapping;
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
        List<SeatArea> areas = seatClient.areaOccupancy();
        if (areas.isEmpty()) {
            return ApiResponse.error(ApiResponse.ERR_SEAT_UNREACHABLE, "座位系统暂不可达");
        }
        return ApiResponse.ok(Map.of("count", areas.size(), "areas", areas));
    }
}
