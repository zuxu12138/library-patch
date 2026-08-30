package cn.dlut.librarypatch.web;

import cn.dlut.librarypatch.common.ApiResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/**
 * 全局异常兜底（契约①信封的最后一道防线）。
 * 任何未被 Controller 捕获的异常都不允许漏出 Spring 默认错误 JSON
 * （含 path/timestamp/stack 等技术细节），统一折成 {code,msg,data}。
 * msg 固定化，不携带 e.getMessage()。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 参数绑定失败: ?page=abc 之类 → 40001 */
    @ExceptionHandler({MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    public ApiResponse<Void> badRequest(Exception e) {
        log.warn("请求参数非法: {}", e.getMessage());
        return ApiResponse.error(ApiResponse.ERR_BAD_REQUEST, "请求参数非法");
    }

    /** 兜底: 其余一切异常 → 50001, msg 不带技术细节 */
    @ExceptionHandler(Exception.class)
    public ApiResponse<Void> unexpected(Exception e) {
        log.error("未预期异常: {}", e.toString(), e);
        return ApiResponse.error(ApiResponse.ERR_OPAC_TIMEOUT, "数据服务内部错误，请稍后再试");
    }
}
