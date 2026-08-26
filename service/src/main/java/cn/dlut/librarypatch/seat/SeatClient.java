package cn.dlut.librarypatch.seat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
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
            @Value("${library.seat.libid}") String libid) {
        this.libid = libid;
        this.rest = RestClient.builder().baseUrl(baseUrl).build();
    }

    /** 拉取全部区域的实时占用。失败返回空列表，不抛异常。 */
    public List<SeatArea> areaOccupancy() {
        try {
            byte[] bytes = rest.get()
                    .uri("Seatresv/GetSeatCount.asp?libid={id}", libid)
                    .retrieve()
                    .body(byte[].class);
            return parse(bytes);
        } catch (Exception e) {
            log.warn("座位占用查询失败: {}", e.toString());
            return List.of();
        }
    }

    private List<SeatArea> parse(byte[] bytes) throws Exception {
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
