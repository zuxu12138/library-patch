package cn.dlut.librarypatch.common;

/**
 * 统一响应信封 {code, msg, data}。所有 REST 接口成功/失败都用它。
 * 错误码段位（见 docs/接口契约.md）：
 *   0            成功
 *   40001-40099  请求错误(参数缺失/非法)
 *   50001-50099  Java 数据层(A)
 *   60001-60099  Agent 层(B/C)
 */
public record ApiResponse<T>(int code, String msg, T data) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> error(int code, String msg) {
        return new ApiResponse<>(code, msg, null);
    }

    // 常用错误码常量
    public static final int ERR_BAD_REQUEST = 40001;    // 参数缺失/非法
    public static final int ERR_OPAC_TIMEOUT = 50001;   // OPAC 超时/不可达
    public static final int ERR_SEAT_UNREACHABLE = 50002; // 座位系统不可达
}
