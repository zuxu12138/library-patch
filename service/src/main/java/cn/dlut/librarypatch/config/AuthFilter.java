package cn.dlut.librarypatch.config;

import cn.dlut.librarypatch.common.ApiResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 契约共用 · 内部鉴权：校验 X-Internal-Token。
 * - token 配置为空（本地开发）时直接放行，不挡路。
 * - token 非空（公网部署）时，请求头不匹配则 401 + 统一信封错误体。
 * 健康检查 /api/health 永远放行，便于探活。
 */
@Order(2)
@Component
public class AuthFilter extends OncePerRequestFilter {

    public static final String TOKEN_HEADER = "X-Internal-Token";
    /** 40100: 鉴权失败(契约 400xx 段保留给参数错误, 鉴权单列 401xx) */
    public static final int ERR_UNAUTHORIZED = 40100;

    private final String expectedToken;
    private final ObjectMapper mapper = new ObjectMapper();

    public AuthFilter(@Value("${internal.token:}") String expectedToken) {
        this.expectedToken = expectedToken == null ? "" : expectedToken.trim();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp,
                                    FilterChain chain) throws ServletException, IOException {
        // 本地开发：未配 token 则放行
        if (expectedToken.isEmpty()) {
            chain.doFilter(req, resp);
            return;
        }
        // 健康检查放行
        if ("/api/health".equals(req.getRequestURI())) {
            chain.doFilter(req, resp);
            return;
        }
        String got = req.getHeader(TOKEN_HEADER);
        if (constantTimeEquals(expectedToken, got)) {
            chain.doFilter(req, resp);
        } else {
            resp.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            resp.setContentType(MediaType.APPLICATION_JSON_VALUE);
            resp.setCharacterEncoding("UTF-8");
            // 走 ApiResponse 序列化, 不手写 JSON 字符串——信封加字段时不会漏
            resp.getWriter().write(mapper.writeValueAsString(
                    ApiResponse.error(ERR_UNAUTHORIZED, "invalid internal token")));
        }
    }

    /** 定长比较, 避免 token 逐字节早退带来的时序侧信道 */
    private static boolean constantTimeEquals(String expected, String got) {
        if (got == null) {
            return false;
        }
        return MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8),
                got.getBytes(StandardCharsets.UTF_8));
    }
}
