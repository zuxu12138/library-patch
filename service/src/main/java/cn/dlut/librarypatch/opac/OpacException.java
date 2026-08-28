package cn.dlut.librarypatch.opac;

/**
 * OPAC 上游调用失败（超时/5xx/解析失败）。抛出即不缓存，
 * 避免"OPAC 挂掉时的空结果被 Caffeine 缓存 5 分钟"的坑。
 */
public class OpacException extends RuntimeException {
    public OpacException(String message, Throwable cause) {
        super(message, cause);
    }
}
