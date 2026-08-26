package cn.dlut.librarypatch;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

/**
 * 大工图书馆补丁 - 数据服务层入口。
 * 职责：把混乱的 OPAC / 座位第三方接口封装成干净、稳定的内部 REST，供 Python agent 调用。
 * agent 不直接碰第三方接口。
 */
@EnableCaching
@SpringBootApplication
public class LibraryPatchApplication {
    public static void main(String[] args) {
        SpringApplication.run(LibraryPatchApplication.class, args);
    }
}
