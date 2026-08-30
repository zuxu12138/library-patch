package cn.dlut.librarypatch.opac;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
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
    private final long totalTimeoutMs;

    public OpacClient(
            @Value("${library.opac.base-url}") String baseUrl,
            @Value("${library.opac.search-path}") String searchPath,
            @Value("${library.opac.index-name}") String indexName,
            @Value("${library.opac.timeout-ms}") int timeoutMs,
            @Value("${library.opac.max-retries}") int maxRetries,
            @Value("${library.opac.total-timeout-ms:20000}") long totalTimeoutMs) {
        this.searchPath = searchPath;
        this.indexName = indexName;
        this.maxRetries = maxRetries;
        // 总预算: 重试全部计入, 上游卡死时单请求最坏 ~totalTimeoutMs, 不再 3×15s 拖死 Tomcat 线程池
        this.totalTimeoutMs = totalTimeoutMs;
        // 超时必须接线——配置里写了不代表生效，裸 RestClient 默认无超时,OPAC 卡死会拖垮线程池
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(timeoutMs);
        factory.setReadTimeout(timeoutMs);
        this.rest = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }

    /**
     * 检索馆藏。结果缓存 5 分钟（application.yml opacSearch），相同查询短期不重复打 OPAC。
     * 失败抛 OpacException——异常不进缓存,绝不让"OPAC 挂掉时的空结果"被缓存 5 分钟。
     */
    @Cacheable(cacheNames = "opacSearch", key = "#query.trim() + ':' + #page + ':' + #pageSize")
    public BookSearchResult search(String query, int page, int pageSize) {
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
        } catch (OpacException e) {
            throw e;
        } catch (Exception e) {
            log.warn("OPAC 检索失败 query={}: {}", query, e.toString());
            throw new OpacException("OPAC 检索失败: " + e.getMessage(), e);
        }
    }

    /** 分类重试：超时/429/5xx 退避重试；4xx 直接放弃（不重试）。
     *  全部重试共享 totalTimeoutMs 总预算; 线程被中断(shutdown)立即抛, 不再继续打上游。 */
    private String postWithRetry(Map<String, Object> body) {
        long deadline = System.nanoTime() + totalTimeoutMs * 1_000_000L;
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
                if (System.nanoTime() + backoff * 1_000_000L > deadline) {
                    break; // 总预算不够下一次重试, 直接失败
                }
                sleepInterruptibly(backoff);
                backoff *= 2;
            }
        }
        throw last != null ? last : new IllegalStateException("OPAC 请求失败");
    }

    private static void sleepInterruptibly(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            // 中断语义: 收到 shutdown 信号后不再继续重试打上游
            throw new OpacException("重试被中断", ie);
        }
    }

    /** 解析 OPAC 响应。包私有以便 JUnit 直接测解析逻辑。 */
    BookSearchResult parse(String raw) throws Exception {
        if (raw == null || raw.isBlank()) {
            throw new OpacException("OPAC 返回空响应", null);
        }
        JsonNode data = mapper.readTree(raw).path("data");
        List<Book> books = new ArrayList<>();
        JsonNode list = data.path("dataList");
        if (list.isArray()) {
            for (JsonNode n : list) {
                books.add(toBook(n));
            }
        }
        // total 优先取 actualTotal, 兜底 total, 都没有才退化为当前页条数
        int total = data.path("actualTotal").asInt(data.path("total").asInt(books.size()));
        return new BookSearchResult(total, books);
    }

    Book toBook(JsonNode n) {
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

    /** holdings 是被转义的 JSON 字符串数组，需二次解析。解析失败降级为空 holdings,不打断整本书。 */
    List<Holding> parseHoldings(String holdingsJson) {
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
