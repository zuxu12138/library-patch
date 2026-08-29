package cn.dlut.librarypatch.config;

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

    private final String expectedToken;

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
        if (expectedToken.equals(got)) {
            chain.doFilter(req, resp);
        } else {
            resp.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            resp.setContentType(MediaType.APPLICATION_JSON_VALUE);
            resp.setCharacterEncoding("UTF-8");
            resp.getWriter().write("{\"code\":40100,\"msg\":\"invalid internal token\",\"data\":null}");
        }
    }
}
