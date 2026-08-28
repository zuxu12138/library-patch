package cn.dlut.librarypatch.seat;

/**
 * 座位系统上游调用失败（超时/不可达/解析失败）。
 * 失败必须显式暴露给上层——空列表会被误读成"全校没人"。
 */
public class SeatException extends RuntimeException {
    public SeatException(String message, Throwable cause) {
        super(message, cause);
    }
}
