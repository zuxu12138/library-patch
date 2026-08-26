package cn.dlut.librarypatch.opac;

/**
 * 单册馆藏（一本书可能有多册）。字段来自 OPAC holdings 内嵌 JSON。
 *
 * @param callNo   索书号, 如 "TP181 Z812"
 * @param location 馆藏位置, 如 "总馆 - 令希图书馆402室"
 * @param status   在馆状态, 如 "可借" / "借出"
 * @param available 是否可借 (circStatus==0)
 * @param barCode  条码号
 */
public record Holding(
        String callNo,
        String location,
        String status,
        boolean available,
        String barCode
) {}
