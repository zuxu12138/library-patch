# 接口真实响应样例(供 UI 设计参考)

> 2026-08-28 从运行中的系统实测抓取。所有接口统一信封 `{code, msg, data}`,
> `code=0` 成功;非 0 时 `data=null`,`msg` 可直接展示给用户。
> 前端只需关心 `data` 层。

## POST /findbook/search — 找书

请求体: `{"query": "深度学习", "page": 1, "page_size": 10}`(另需请求头 `X-User-Id`)。
- `total` 是真实总命中数,前端分页用它;`books` 只是当前页
- `holdings[]`: 每册一行,`available=true` 绿色徽标「可借」,`false` 灰色「已借出」
- 书卡核心字段: title / author / publisher / pubYear / classNo(中图法分类) / callNos(索书号)

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "books": [
      {
        "bibId": "m5119ba75115db76c368c25d6950959bf",
        "title": "深度学习.精装版",
        "author": "(美) 伊恩·古德费洛, (加) 约书亚·本吉奥, (加) 亚伦·库维尔著",
        "publisher": "人民邮电出版社",
        "pubYear": "2021",
        "isbn": "978-7-115-55286-0",
        "classNo": "TP181",
        "callNos": [
          "TP181 G651B"
        ],
        "abstractText": "本书内容包括3个部分：第1部分介绍基本的数学工具和机器学习的概念，它们是深度学习的预备知识；第2部分系统深入地讲解现今已……",
        "docType": "中文图书",
        "holdings": [
          {
            "callNo": "TP181 G651B",
            "location": "总馆 - 令希图书馆302室",
            "status": "可借",
            "available": true,
            "barCode": "C2694837"
          },
          {
            "callNo": "TP181 G651B",
            "location": "开发区校区分馆 - 开发区馆三层借阅区",
            "status": "借出",
            "available": false,
            "barCode": "C2553196"
          }
        ]
      }
    ],
    "pageSize": 2,
    "page": 1,
    "total": 6780
  }
}
```

## POST /seat/predict — 座位预测

请求体: `{"weekday": 4, "hour": 16}`(weekday 1=周一…7=周日;hour 0-23)。
- `ranking` 已按预测占用率**升序**排好,越靠前越推荐
- `avg_occupancy_rate` 0~1,渲染成百分比进度条/柱子
- `free_now`/`total` 是实时空闲数,可标注「当前空 80/80」;`samples` 是历史采样点数,少时提示「预测置信度低」
- `realtime_available=false` 时实时字段为 null,UI 应显示「仅历史数据」横幅

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "ranking": [
      {
        "area_name": "103自习室 154/154",
        "avg_occupancy_rate": 0.0,
        "samples": 11,
        "free_now": 154,
        "total": 154
      },
      {
        "area_name": "三层大厅 84/84",
        "avg_occupancy_rate": 0.0,
        "samples": 11,
        "free_now": 84,
        "total": 84
      },
      {
        "area_name": "四层图书阅览区 532/532",
        "avg_occupancy_rate": 0.0,
        "samples": 11,
        "free_now": 532,
        "total": 532
      }
    ],
    "realtime_available": true
  }
}
```

## POST /knowledge/graph — 引用关系图

请求体: `{"paper_id": "..."}`。
- `nodes[0]` 是中心论文(没有 title 字段,UI 可用「当前论文」占位);其余节点有 title/year
- `edges` 的 source/target 是 paperId;力导向图渲染,中心节点用强调色
- 限流降级时返回 `{"nodes": [], "edges": [], "error": "..."}`,要展示空态+错误文案

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "nodes": [
      {
        "paperId": "649def34f8be52c8b66281af98ae884c09aef38b"
      },
      {
        "paperId": "1fec9d41d372267b4474f18cbeadd806c8b67adb",
        "title": "Extracting Scientific Figures with Distantly Supervised Neural Networks",
        "year": 2018
      },
      {
        "paperId": "921b2958cac4138d188fd5047aa12bbcf37ac867",
        "title": "Content-Based Citation Recommendation",
        "year": 2018
      },
      {
        "paperId": "2264e14e35dc5a3db93437bc408a03171af8c59d",
        "title": "The AI2 system at SemEval-2017 Task 10 (ScienceIE): semi-supervised end-to-end entity and relation extraction",
        "year": 2017
      }
    ],
    "edges": [
      {
        "source": "649def34f8be52c8b66281af98ae884c09aef38b",
        "target": "1fec9d41d372267b4474f18cbeadd806c8b67adb"
      },
      {
        "source": "649def34f8be52c8b66281af98ae884c09aef38b",
        "target": "921b2958cac4138d188fd5047aa12bbcf37ac867"
      },
      {
        "source": "649def34f8be52c8b66281af98ae884c09aef38b",
        "target": "2264e14e35dc5a3db93437bc408a03171af8c59d"
      }
    ]
  }
}
```

## POST /knowledge/summarize — 论文摘要

请求体: `{"paper_id": "..."}`。
- 无 LLM 时降级: 直接返回论文原始字段(title/abstract/authors),前端按原文展示即可
- S2 限流时返回 `{"error": "..."}`,展示错误文案,**不再 500**

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
    "title": "Construction of the Literature Graph in Semantic Scholar",
    "year": 2018,
    "openAccessPdf": {
      "url": "https://www.aclweb.org/anthology/N18-3011.pdf",
      "status": "GOLD",
      "license": "CCBY",
      "disclaimer": "Notice: Paper or abstract available at https://arxiv.org/abs/1805.02262, which is subject to the license by the author or copyright owner provided with this content. Please go to the source to verify the license and copyright information for your use."
    },
    "authors": [
      {
        "authorId": "145585097",
        "name": "Bridger Waleed Ammar"
      },
      {
        "authorId": "3458736",
        "name": "Dirk Groeneveld"
      },
      {
        "authorId": "1857797",
        "name": "Chandra Bhagavatula"
      },
      {
        "authorId": "46181066",
        "name": "Iz Beltagy"
      },
      {
        "authorId": "46230609",
        "name": "Miles Crawford"
      },
      {
        "authorId": "145612610",
        "name": "Doug Downey"
      },
      {
        "authorId": "38092776",
        "name": "Jason Dunkelberger"
      },
      {
        "authorId": "143718836",
        "name": "Ahmed Elgohary"
      },
      {
        "authorId": "46411828",
        "name": "Sergey Feldman"
      },
      {
        "authorId": "4480314",
        "name": "Vu A. Ha"
      },
      {
        "authorId": "143967880",
        "name": "Rodney Michael Kinney"
      },
      {
        "authorId": "41018147",
        "name": "Sebastian Kohlmeier"
      },
      {
        "authorId": "46258841",
        "name": "Kyle Lo"
      },
      {
        "authorId": "144240185",
        "name": "Tyler C. Murray"
      },
      {
        "authorId": "46256862",
        "name": "Hsu-Han Ooi"
      },
      {
        "authorId": "39139825",
        "name": "Matthew E. Peters"
      },
      {
        "authorId": "39561369",
        "name": "Joanna L. Power"
      },
      {
        "authorId": "46181683",
        "name": "Sam Skjonsberg"
      },
      {
        "authorId": "31860505",
        "name": "Lucy Lu Wang"
      },
      {
        "authorId": "46212260",
        "name": "Christopher Wilhelm"
      },
      {
        "authorId": "2112339497",
        "name": "Zheng Yuan"
      },
      {
        "authorId": "15292561",
        "name": "Madeleine van Zuylen"
      },
      {
        "authorId": "1741101",
        "name": "Oren Etzioni"
      }
    ],
    "abstract": "We describe a deployed scalable system for organizing published scientific literature into a heterogeneous graph to facilitate algorithmic manipulation and discovery. The resulting literature graph consists of more than 280M nodes, representing papers, authors, entities and various interactions between them (e.g., authorships, citations, entity mentions). We reduce literature graph construction into familiar NLP tasks (e.g., entity extraction and linking), point out research challenges due to differences from standard formulations of these tasks, and report empirical results for each task. The methods described in this paper are used to enable semantic features in www.semanticscholar.org."
  }
}
```

## 反馈接口(三个页面共用)

`POST /findbook/feedback` · `/seat/feedback` · `/memory/feedback`,请求体 `{"feedback": "..."}`。

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "memory_ids": [],
    "llm_available": false
  }
}
```

- `llm_available=false` 时前端诚实提示:「已收到,但偏好记忆未启用(未配置模型),本次不会被记住」
- `true` 且 `memory_ids` 非空:显示「已记住,下次检索会按你的偏好调整」

## 错误信封样例(OPAC 挂掉时)

```json
{"code": 50001, "msg": "OPAC 检索服务暂时不可用,请稍后再试", "data": null}
```

常见错误码: `40001` 参数缺失 · `50001` OPAC/数据层故障 · `50002` 座位系统故障 · `60001` 服务未就绪。
