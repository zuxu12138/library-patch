package cn.dlut.librarypatch.web;

import cn.dlut.librarypatch.common.ApiResponse;
import cn.dlut.librarypatch.opac.Book;
import cn.dlut.librarypatch.opac.OpacClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 书目检索 API（契约①）。供 Python agent 调用，屏蔽 OPAC 脏细节。
 * 响应统一走 {code,msg,data} 信封；trace_id 由 TraceFilter 自动处理。
 */
@RestController
public class BookController {

    private final OpacClient opacClient;

    public BookController(OpacClient opacClient) {
        this.opacClient = opacClient;
    }

    /** GET /api/books/search?q=机器学习&page=1&pageSize=10 */
    @GetMapping("/api/books/search")
    public ApiResponse<Map<String, Object>> search(
            @RequestParam(value = "q", required = false) String query,
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "pageSize", defaultValue = "10") int pageSize) {
        if (query == null || query.isBlank()) {
            return ApiResponse.error(ApiResponse.ERR_BAD_REQUEST, "缺少查询参数 q");
        }
        List<Book> books = opacClient.search(query, page, pageSize);
        return ApiResponse.ok(Map.of(
                "total", books.size(),
                "page", page,
                "pageSize", pageSize,
                "books", books
        ));
    }

    /** 健康检查 */
    @GetMapping("/api/health")
    public ApiResponse<Map<String, String>> health() {
        return ApiResponse.ok(Map.of("status", "ok"));
    }
}
