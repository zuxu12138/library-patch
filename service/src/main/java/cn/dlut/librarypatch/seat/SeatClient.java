package cn.dlut.librarypatch.seat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 座位系统客户端（RestClient）。封装 360banke/晓图 GetSeatCount.asp。
 *
 * 关键事实（踩坑换来的，勿改）：
 *  - 强制按 GBK 解码——别信响应头 charset，老 ASP 站点经常标错。
 *  - 区域名形如 "301阅览室 143/143"，尾部 free/total 需解析。
 *  单座级 / 历史序列由 Python 采集器负责，本层只给"现在"。
 */
@Component
public class SeatClient {

    private static final Logger log = LoggerFactory.getLogger(SeatClient.class);
    private static final Charset GBK = Charset.forName("GBK");

    private final RestClient rest;
    private final ObjectMapper mapper = new ObjectMapper();
    private final String libid;

    public SeatClient(
            @Value("${library.seat.base-url}") String baseUrl,
            @Value("${library.seat.libid}") String libid,
            @Value("${library.seat.timeout-ms}") int timeoutMs) {
        this.libid = libid;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(timeoutMs);
        factory.setReadTimeout(timeoutMs);
        this.rest = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }

    /** 拉取全部区域的实时占用。失败抛 SeatException——空列表会被误读成"全校没人"。 */
    public List<SeatArea> areaOccupancy() {
        try {
            byte[] bytes = rest.get()
                    .uri("Seatresv/GetSeatCount.asp?libid={id}", libid)
                    .retrieve()
                    .body(byte[].class);
            List<SeatArea> areas = parse(bytes);
            if (areas.isEmpty()) {
                throw new SeatException("座位系统返回空数据", null);
            }
            return areas;
        } catch (SeatException e) {
            throw e;
        } catch (Exception e) {
            log.warn("座位占用查询失败: {}", e.toString());
            throw new SeatException("座位占用查询失败: " + e.getMessage(), e);
        }
    }

    /** 包私有以便 JUnit 直接测解析逻辑。 */
    List<SeatArea> parse(byte[] bytes) throws Exception {
        List<SeatArea> areas = new ArrayList<>();
        if (bytes == null || bytes.length == 0) {
            return areas;
        }
        // 强制 GBK 解码，不看响应头
        JsonNode root = mapper.readTree(new String(bytes, GBK));
        Map<String, String> libByMap = new HashMap<>();
        for (JsonNode m : root.path("maplist")) {
            libByMap.put(m.path("id").asText(), m.path("libcode").asText(""));
        }
        for (JsonNode a : root.path("maparea")) {
            String mapId = a.path("mapid").asText();
            String name = a.path("name").asText("");
            int total = a.path("ct").asInt(0);
            int free = parseFree(name, total);
            areas.add(new SeatArea(
                    mapId, name, libByMap.getOrDefault(mapId, ""),
                    total, free, Math.max(0, total - free)));
        }
        return areas;
    }

    /** 拉取某楼层的单座级实时状态(含平面图坐标)。失败抛 SeatException。 */
    public List<SeatItem> seatMap(String mapId) {
        try {
            byte[] bytes = rest.get()
                    .uri("Seatresv/GetSeatList.asp?libid={id}&mapid={mid}", libid, mapId)
                    .retrieve()
                    .body(byte[].class);
            return parseSeatList(bytes);
        } catch (SeatException e) {
            throw e;
        } catch (Exception e) {
            log.warn("单座查询失败 mapid={}: {}", mapId, e.toString());
            throw new SeatException("单座查询失败: " + e.getMessage(), e);
        }
    }

    /** 包私有以便 JUnit 直接测解析逻辑。 */
    List<SeatItem> parseSeatList(byte[] bytes) throws Exception {
        List<SeatItem> seats = new ArrayList<>();
        if (bytes == null || bytes.length == 0) {
            return seats;
        }
        JsonNode root = mapper.readTree(new String(bytes, GBK));
        for (JsonNode s : root.path("seats")) {
            // mappos 形如 "5457,2379", 解析失败丢 (0,0) 外 —— 直接跳过, 别把座位画到原点上
            String[] pos = s.path("mappos").asText("").split(",");
            if (pos.length != 2) {
                continue;
            }
            try {
                seats.add(new SeatItem(
                        s.path("seatid").asText(""),
                        s.path("seatnum").asText(""),
                        Integer.parseInt(pos[0].trim()),
                        Integer.parseInt(pos[1].trim()),
                        "true".equalsIgnoreCase(s.path("isbusy").asText("")),
                        s.path("seattype").asText(""),
                        s.path("status").asText("")
                ));
            } catch (NumberFormatException ignored) {
                // 坐标坏了的座位不上图
            }
        }
        return seats;
    }

    /** 从区域名 "301阅览室 143/143" 解析空闲数；解析不到按满座（free=0）。 */
    private int parseFree(String name, int total) {
        if (name != null && name.contains("/")) {
            String tail = name.trim();
            tail = tail.substring(tail.lastIndexOf(' ') + 1);
            try {
                return Integer.parseInt(tail.split("/")[0]);
            } catch (NumberFormatException ignored) {
                // fall through
            }
        }
        return 0;
    }
}
