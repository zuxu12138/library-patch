package cn.dlut.librarypatch.opac;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * OpacClient 解析逻辑测试(不碰网络): 内嵌 holdings 二次解析 + total 分页字段。
 */
class OpacClientTest {

    private final OpacClient client = new OpacClient("http://unused", "/p/", "idx.opac", 15000, 0, 20000);

    @Test
    void parseExtractsBooksTotalAndHoldings() throws Exception {
        String raw = """
                {"data":{"total":57,"actualTotal":57,"dataList":[
                  {"bibId":"b1","title":"深度学习","author":"伊恩·古德费洛","publisher":"人民邮电出版社",
                   "pub_year":"2021","isbn":"978-7-115-55286-0","classno":"TP181",
                   "callno":["TP181 G651B"],"docTypeDesc":"中文图书","abstract":"...",
                   "holdings":"[{\\"callNo\\":\\"TP181 G651B\\",\\"location\\":\\"令希302\\",\\"status\\":\\"可借\\",\\"circStatus\\":0,\\"barCode\\":\\"C1\\"}]"}
                ]}}
                """;
        BookSearchResult result = client.parse(raw);

        assertEquals(57, result.total());          // 分页必须用真实 total, 不是 books.size()
        assertEquals(1, result.books().size());
        var book = result.books().get(0);
        assertEquals("深度学习", book.title());
        assertEquals(java.util.List.of("TP181 G651B"), book.callNos());
        assertEquals(1, book.holdings().size());
        assertEquals("令希302", book.holdings().get(0).location());
        assertTrue(book.holdings().get(0).available()); // circStatus=0 → 可借
    }

    @Test
    void parseFallsBackToPageSizeWhenNoTotalField() throws Exception {
        String raw = """
                {"data":{"dataList":[{"bibId":"b1","title":"t","callno":[],"holdings":"[]"}]}}
                """;
        BookSearchResult result = client.parse(raw);
        assertEquals(1, result.total());
        assertEquals(1, result.books().size());
    }

    @Test
    void emptyRawThrowsInsteadOfSilentEmpty() {
        // 失败语义: 空响应是故障, 必须抛, 不能伪装成"没查到"
        assertThrows(OpacException.class, () -> client.parse(""));
    }

    @Test
    void malformedHoldingsDegradesToEmptyList() {
        var holdings = client.parseHoldings("not-json{");
        assertTrue(holdings.isEmpty()); // 单本书 holdings 坏了不拖垮整页
    }
}
