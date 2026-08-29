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

    @Test
    void parsesSeatListWithMapPositions() throws Exception {
        String json = """
                {"mapid":"2498","seats":[
                  {"seatid":"A1","seatnum":"001","mappos":"5457,2379","isbusy":"false","seattype":"电源|台灯","status":"不可预约"},
                  {"seatid":"A2","seatnum":"002","mappos":"5331,2442","isbusy":"true","seattype":"","status":"已占用"},
                  {"seatid":"A3","seatnum":"003","mappos":"bad","isbusy":"false","seattype":"","status":""}
                ]}
                """;
        List<SeatItem> seats = client.parseSeatList(json.getBytes(GBK));

        assertEquals(2, seats.size()); // 坐标坏的座位不上图
        assertEquals(5457, seats.get(0).x());
        assertEquals(2379, seats.get(0).y());
        assertFalse(seats.get(0).busy());
        assertTrue(seats.get(1).busy());
        assertEquals("电源|台灯", seats.get(0).seatType());
    }
}
