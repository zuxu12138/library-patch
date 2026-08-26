package cn.dlut.librarypatch.opac;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * OPAC 检索客户端（RestClient）。封装 POST /meta-local/opac/search/，
 * 把混乱的返回结构（含内嵌 holdings JSON 字符串）解析成干净的 Book 列表。
 *
 * 关键事实（踩坑换来的，勿改）：
 *  - 必须用 queryFieldList 结构(field=all)，裸 q 会返回全库不过滤。
 *  - search-path 尾斜杠必须有。
 *  - holdings 是被转义的 JSON 字符串，需二次解析。
 * 重试策略：超时/429/5xx 退避重试；4xx 不重试（一股脑退避只会放大故障）。
 */
@Component
public class OpacClient {

    private static final Logger log = LoggerFactory.getLogger(OpacClient.class);

    private final RestClient rest;
    private final ObjectMapper mapper = new ObjectMapper();
    private final String searchPath;
    private final String indexName;
    private final int maxRetries;

    public OpacClient(
            @Value("${library.opac.base-url}") String baseUrl,
            @Value("${library.opac.search-path}") String searchPath,
            @Value("${library.opac.index-name}") String indexName,
            @Value("${library.opac.max-retries}") int maxRetries) {
        this.searchPath = searchPath;
        this.indexName = indexName;
        this.maxRetries = maxRetries;
        this.rest = RestClient.builder().baseUrl(baseUrl).build();
    }

    /**
     * 检索馆藏。结果缓存 5 分钟（application.yml opacSearch），相同查询短期不重复打 OPAC。
     * 解析失败返回空列表，绝不抛异常打断上层。
     */
    @Cacheable(cacheNames = "opacSearch", key = "#query + ':' + #page + ':' + #pageSize")
    public List<Book> search(String query, int page, int pageSize) {
        // OPAC 真实检索结构：queryFieldList，field="all" 为全字段检索。裸 q 会返回全库不过滤。
        Map<String, Object> body = Map.of(
                "page", page,
                "pageSize", pageSize,
                "indexName", indexName,
                "queryFieldList", List.of(Map.of(
                        "logic", 0, "field", "all", "values", List.of(query)))
        );
        try {
            String raw = postWithRetry(body);
            return parse(raw);
        } catch (Exception e) {
            log.warn("OPAC 检索失败 query={}: {}", query, e.toString());
            return List.of();
        }
    }

    /** 分类重试：超时/429/5xx 退避重试；4xx 直接放弃（不重试）。 */
    private String postWithRetry(Map<String, Object> body) {
        long backoff = 500;
        RuntimeException last = null;
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                return rest.post()
                        .uri(searchPath)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(body)
                        .retrieve()
                        .body(String.class);
            } catch (HttpClientErrorException e) {
                // 4xx：429 可退避，其余客户端错误不重试
                if (e.getStatusCode().value() == 429) {
                    last = e;
                } else {
                    throw e;
                }
            } catch (HttpServerErrorException | ResourceAccessException e) {
                // 5xx / 超时/连接失败：可退避重试
                last = e;
            }
            if (attempt < maxRetries) {
                sleep(backoff);
                backoff *= 2;
            }
        }
        throw last != null ? last : new IllegalStateException("OPAC 请求失败");
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }

    private List<Book> parse(String raw) throws Exception {
        List<Book> books = new ArrayList<>();
        if (raw == null || raw.isBlank()) {
            return books;
        }
        JsonNode list = mapper.readTree(raw).path("data").path("dataList");
        if (list.isArray()) {
            for (JsonNode n : list) {
                books.add(toBook(n));
            }
        }
        return books;
    }

    private Book toBook(JsonNode n) {
        List<String> callNos = new ArrayList<>();
        for (JsonNode c : n.path("callno")) {
            callNos.add(c.asText());
        }
        return new Book(
                text(n, "bibId"), text(n, "title"), text(n, "author"),
                text(n, "publisher"), text(n, "pub_year"), text(n, "isbn"),
                text(n, "classno"), callNos, text(n, "abstract"),
                text(n, "docTypeDesc"),
                parseHoldings(n.path("holdings").asText(""))
        );
    }

    /** holdings 是被转义的 JSON 字符串数组，需二次解析。 */
    private List<Holding> parseHoldings(String holdingsJson) {
        List<Holding> result = new ArrayList<>();
        if (holdingsJson == null || holdingsJson.isBlank() || "[]".equals(holdingsJson)) {
            return result;
        }
        try {
            for (JsonNode h : mapper.readTree(holdingsJson)) {
                result.add(new Holding(
                        h.path("callNo").asText(""),
                        h.path("location").asText(""),
                        h.path("status").asText(""),
                        h.path("circStatus").asInt(-1) == 0,
                        h.path("barCode").asText("")
                ));
            }
        } catch (Exception e) {
            log.debug("holdings 解析失败: {}", e.toString());
        }
        return result;
    }

    private static String text(JsonNode n, String field) {
        JsonNode v = n.path(field);
        return v.isMissingNode() || v.isNull() ? "" : v.asText();
    }
}
