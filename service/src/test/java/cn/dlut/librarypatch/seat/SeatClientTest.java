package cn.dlut.librarypatch.seat;

import org.junit.jupiter.api.Test;

import java.nio.charset.Charset;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * SeatClient 解析逻辑测试(不碰网络): GBK 强制解码 + "301阅览室 143/143" 名称解析。
 */
class SeatClientTest {

    private static final Charset GBK = Charset.forName("GBK");

    private final SeatClient client = new SeatClient("http://unused", "dlut", 10000);

    @Test
    void parsesGbkResponseWithAreas() throws Exception {
        String json = """
                {"maplist":[{"id":"2498","libcode":"bochuan"}],
                 "maparea":[{"mapid":"2498","name":"301阅览室 100/143","ct":143},
                            {"mapid":"2499","name":"401阅览室 140/140","ct":140}]}
                """;
        List<SeatArea> areas = client.parse(json.getBytes(GBK));

        assertEquals(2, areas.size());
        SeatArea first = areas.get(0);
        assertEquals("bochuan", first.libCode());
        assertEquals(143, first.total());
        assertEquals(100, first.free());
        assertEquals(43, first.occupied());
    }

    @Test
    void unparsableNameFallsBackToFull() throws Exception {
        String json = """
                {"maplist":[],"maparea":[{"mapid":"1","name":"坏名字没有斜杠","ct":50}]}
                """;
        List<SeatArea> areas = client.parse(json.getBytes(GBK));
        assertEquals(0, areas.get(0).free());      // 解析不到按满座, 不瞎报有空位
        assertEquals(50, areas.get(0).occupied());
    }

    @Test
    void emptyBytesYieldEmptyList() throws Exception {
        assertTrue(client.parse(new byte[0]).isEmpty());
    }
}
