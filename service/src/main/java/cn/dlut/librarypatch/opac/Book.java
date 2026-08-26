package cn.dlut.librarypatch.opac;

import java.util.List;

/**
 * 一条书目记录（聚合 OPAC search 返回的书目 + 馆藏）。字段对齐 docs/接口契约.md 契约①。
 *
 * @param bibId     书目 ID
 * @param title     题名
 * @param author    著者
 * @param publisher 出版社
 * @param pubYear   出版年
 * @param isbn      ISBN
 * @param classNo   分类号 (中图法)
 * @param callNos   索书号列表
 * @param abstractText 内容摘要
 * @param docType   文献类型描述, 如 "中文图书"
 * @param holdings  各册馆藏 (索书号/架位/在馆状态)
 */
public record Book(
        String bibId,
        String title,
        String author,
        String publisher,
        String pubYear,
        String isbn,
        String classNo,
        List<String> callNos,
        String abstractText,
        String docType,
        List<Holding> holdings
) {}
