# C 角色(粘合侧)进度说明

> 写给 A(数据侧)、B(大脑侧)同学看的进度同步。最后更新:2026-08-23。
>
> 结论先行:**C 侧功能 + 前端已全部实现并自测通过,可以开始联调;当前卡在等 B 的 `agent.core` 与 A 的 Java 服务/座位库到位。**

---

## 一、总览

| 维度 | 状态 |
|---|---|
| 后端(agent 层) | ✅ 完成,37 个测试全绿 |
| 前端(web) | ✅ 三页功能完成,UI 已按大工 VI 重构(重构改动待提交) |
| 依赖 B | ⚠️ `agent.core.agent_loop.AgentLoop` 未交付,后端启动后功能路由返回「服务未就绪」 |
| 依赖 A | ⚠️ Java 服务未启动、`seats.db` 座位库未就位、`seat_snapshots` schema 待确认 |
| 是否可联调 | ✅ 接口契约已全部按 `docs/接口契约.md` 实现,三方拼一起即可跑通 |

---

## 二、后端(agent 层)已完成

全部按三条接口契约实现,DI(依赖注入)+ 测试替身隔离 B/A 未交付部分,可独立自测。

| 文件 | 说明 | 状态 |
|---|---|---|
| `agent/service_client.py` | 调 Java 层,分类重试(超时/5xx/429 退避,4xx 不重试),注入 `X-Trace-Id`/`X-Internal-Token`,信封解析 | ✅ |
| `agent/features/findbook/service.py` | 找书,注册 `search_books` 工具,服务不可用降级 | ✅ |
| `agent/features/knowledge_map/` | 知识地图:SemanticScholarClient(429 退避)+ S2 缓存 + 引用图/摘要工具 | ✅ |
| `agent/features/seat_predict/service.py` | 座位预测笨基线:历史占用率排序,只读连接 + busy_timeout | ✅ |
| `agent/benchmark/harness.py` | 04 赛道指标面板:token/延迟/记忆命中率聚合 | ✅ |
| `agent/main.py` | FastAPI 入口 + 8 条路由 + 信封 + 异常处理 + 依赖注入挂点 | ✅ |
| `agent/config.py` / `.env.example` / `requirements.txt` | 共享文件(C 主维护,已留 A/B 追加注释标记) | ✅ |
| `agent/tests/` | 37 个测试,`FakeAgentLoop` 替身严格对齐契约② | ✅ |

**测试**:仓库根目录执行 `python -m pytest agent/tests -v`,37 passed。本机 Anaconda 环境的 `hydra` 插件会崩,需加 `-p no:hydra_pytest`。

---

## 三、前端(web)已完成

Vue 3 + Vite + TS,无 CSS 框架,主题色用 CSS 变量管理。路由三页:`/findbook`、`/knowledge`、`/seat`。

| 页面/模块 | 说明 |
|---|---|
| 顶部导航 | 固定 64px,大工蓝渐变 + 毛玻璃,系统名 + hover 下划线动画 |
| 找书 `/findbook` | 大搜索框 + 卡片网格结果(封面占位/书名/作者/馆藏状态标签)+ 空状态 |
| 知识地图 `/knowledge` | 论文 ID 展开 ECharts 引用图(根节点大工红高亮) |
| 座位预测 `/seat` | 占用率条形图(绿<50%/橙<80%/红≥80%),实时校正指示灯 |
| 反馈 | 右下角浮动 💬 按钮,点击展开面板 |
| 全局 | 路由 fade-in、卡片 hover 上浮、搜索框 focus 发光、响应式 |

> ⚠️ 说明:UI 重构(大工 VI 主题)的改动目前在 worktree 工作区**尚未提交**,提交后会合入 C 分支。

---

## 四、需要 A/B 配合的事项(重点)

### 需要 B(大脑侧)

1. **`agent/core/agent_loop.py`** —— 这是当前最大阻塞。C 的 `main.py` 在 `startup` 时 import 它,B 交付前功能路由(`/findbook/search` 等)一律返回 `60001 service not ready`。契约②签名 C 已按 `docs/接口契约.md` 严格对齐(`run` / `record_feedback` / `AgentResult` 字段),B 实现落地后直接 import 即可。
2. 若 B 的 `AgentLoop` 签名有调整,**务必三人同步改契约②**,否则 C 的 `main.py`/`FakeAgentLoop` 会对不上。

### 需要 A(数据侧)

1. **Java 服务启动** —— 联调时需 `service/` 起起来,C 的 `service_client.py` 才连得上(`/health` 现在返回 `java: unavailable`)。
2. **`seats.db` 座位库 + `seat_snapshots` 表结构确认** —— C 的座位预测假定 schema 为 `seat_snapshots(weekday, hour, area_name, occupied, total)`,**此表契约未定义,需 A 确认**。若实际字段不同,只需改 `agent/features/seat_predict/service.py` 里的一处 SQL,改动很小。
3. 契约①字段(`/api/books/search`、`/api/seats/now` 的 JSON 结构)C 已按 `docs/接口契约.md` 消费,A 实现落地后直接对接。

---

## 五、分支与提交位置

| 项 | 值 |
|---|---|
| 分支 | `worktree-role-c-glue-impl`(worktree,未合 main) |
| 后端提交 | `a4b2614` … `2d529da` + 修复 `b6a38a4` + `dfe5699` |
| 前端 UI 重构 | 未提交(工作区) |
| 是否动了 A/B 目录 | ❌ 零改动(`service/`、`agent/core/`、`agent/memory/`、`collector/` 均未碰) |

---

## 六、一句话总结

**C 的活干完了、测过了,就等 B 的大脑和 A 的数据到位,三方照契约一拼即可联调。** 有任何接口出入,三人先群里对齐契约再动,避免把队友代码改崩。
