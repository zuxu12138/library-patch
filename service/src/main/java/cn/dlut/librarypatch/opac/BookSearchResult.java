package cn.dlut.librarypatch.opac;

import java.util.List;

/**
 * OPAC 检索结果：总命中数 + 当前页书目。
 * total 来自 OPAC 响应的 total/actualTotal 字段，供前端分页；
 * 不能用 books.size()（那只是当前页条数）。
 */
public record BookSearchResult(int total, List<Book> books) {
}
