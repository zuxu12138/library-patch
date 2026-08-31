# 图书馆补丁 · 技术框架蓝图

> 一个 Agent + 一套反馈记忆 + 三个触角：**找书 (P0) · 知识地图 (P1) · 座位预测 (P2)**。

---

## 项目简介

**图书馆补丁** 是为大连理工大学图书馆打造的一站式智慧服务平台。它把过去需要跑好几个系统才能完成的事（找书、读论文、找座位）整合在一个 Agent 里，并通过一套反馈记忆系统让服务越用越懂你。

### 核心问题

传统图书馆服务存在几个痛点：OPAC 检索只能关键词匹配，找不到"相关推荐"；座位系统只显示当前状态，无法预测哪个区域下午有空；文献之间引用关系零散，无法直观展示知识脉络。这三个问题原本互不相干，但背后可以共用同一套记忆——你越用，它越懂你的阅读风格、座位偏好和检索习惯。

### 三大功能

| 优先级 | 功能 | 一句话描述 |
|---|---|---|
| **P0** | 找书 AI 馆员 | 模糊需求 → 澄清 → 检索 → 索书号/架位/在馆状态 + 相关推荐 |
| **P1** | 个人知识地图 | 文献 → 结构化摘要 → 引用关系图；反馈修正阅读风格 |
| **P2** | 座位预测 | 基于历史占用预测哪层适合你；用户纠错闭环修正 |

### 技术架构

系统采用**双栈分层**设计：

- **Python Agent 层**：产品大脑，负责意图理解、记忆检索、任务编排。使用 FastAPI 暴露 REST 接口，记忆存 SQLite（FTS5 全文检索），LLM 走 OpenAI 兼容协议。
- **Java 数据服务层**：数据闸门，把 OPAC 和座位系统等第三方脏接口封装成干净、稳定的内部 REST。使用 Spring Boot 3.3.5 + RestClient，OPAC 结果用 Caffeine 做 TTL 缓存。
- **采集器**：Python 纯标准库实现，定时从座位系统拉取区域级 + 单座级占用数据，存入 SQLite（WAL 模式），为 P2 预测提供历史时间序列。
- **前端**：Vue 3 + Vite + Tailwind v4 + ECharts，提供对话式找书、引用关系可视化、座位预测交互三个页面。

### 数据流

```
用户 → 前端(Vue) → Python Agent → Java 服务层 → 图书馆数据源 (OPAC / 座位系统)
                              ↓
                         反馈记忆系统 (SQLite + FTS5)
```

Agent 与 Java 层之间带内部 token 鉴权，所有请求携带 `X-Trace-Id` 贯穿两层日志，排查问题时可串联完整链路。

### 关键工程保障

- **幂等反馈**：`user_id + 反馈内容` 算 hash 去重，防止手快多点导致记忆被重复强化
- **多用户隔离**：记忆按 `user_id` 隔离，趁数据少先加，日后不改
- **WAL + busy_timeout**：采集器写 + P2 预测读共享 SQLite，开启 WAL 模式避免 `database is locked`
- **采集器常驻**：macOS launchd `KeepAlive=true`，崩溃自动重启
- **数据备份**：SQLite 持续同步到对象存储（Litestream），或定时在线备份轮转
- **失败 vs 空数据分离**：采集器网络失败和确实无数据分开记录，预测模型不会把超时当成"没人"

### 适用场景

- **01 赛道（大工图书馆）**：端到端解决找书难、座位难、文献散三个真实痛点
- **02 赛道（图书馆补丁）**：在旧系统上打新补丁，最小侵入改造
- **04 赛道（反馈记忆）**：同一套记忆贯穿三个场景，token 成本 / 命中率 / 误用率可量化可演示

## 一、这是什么

给一座几百年的老机构打的现代补丁。核心是一套**反馈记忆系统**：你越用，它越懂你。同一套记忆贯穿三个场景。

| 优先级 | 功能 | 说明 |
|---|---|---|
| **P0** | 找书 AI 馆员 | 模糊需求 → 澄清 → 检索 → 索书号/架位/在馆状态 + 相关推荐；反馈沉淀为偏好 |
| **P1** | 个人知识地图 | 文献 → 结构化摘要 → 引用关系图；反馈修正阅读风格 |
| **P2** | 座位预测 | 基于历史占用预测哪层适合你；用户纠错闭环修正 |

---

## 二、技术栈总览

| 层 | 语言/框架 | 关键依赖 | 存储 |
|---|---|---|---|
| 前端(用户入口) | Vue 3 + Vite | ECharts(知识图谱/指标面板)；无人力则降级 Streamlit | — |
| Agent 层 | Python 3.12 | FastAPI · openai SDK · httpx · pydantic | SQLite(记忆库, FTS5 检索) |
| 数据服务层 | Java 21 | Spring Boot 3.3.5 · **MVC + RestClient**(统一, 不混 WebClient) · Jackson · Caffeine(缓存) | 无状态 |
| 采集器 | Python (纯标准库) | urllib · sqlite3(WAL) | SQLite(时间序列) |
| 测试 | Python | pytest · pytest-asyncio | — |
| 运维 | launchd/systemd(常驻) · **Litestream**(SQLite 持续同步到对象存储) | — | — |
| 环境/工具 | conda · Maven · Homebrew | — | — |

**数据流**：`用户 → 前端(Vue/Streamlit) → Python Agent → Java 服务层 → 图书馆数据源 (OPAC / 座位系统)`
鉴权：agent↔Java 带内部 token；缓存：OPAC 结果 (Java侧 Caffeine) / S2 引用 (Python侧持久缓存)。

**分栈分工**：Python 管 agent 与记忆（生态成熟）；Java 管数据服务（封装脏接口、类型安全）。Agent 只跟 Java 层说话，不直接碰第三方。

---

## 三、目录结构(待建)

```
library-patch/
├── web/            前端 · 用户入口 (Vue 3 + Vite, 或降级 Streamlit)
├── agent/          Python Agent 层 (FastAPI, 产品大脑)
│   ├── core/       共享内核: LLM客户端 / 规划器 / agent循环
│   ├── memory/     反馈记忆核心 (护城河, 04赛道重点)
│   ├── features/   三个功能: findbook / knowledge_map / seat_predict
│   ├── benchmark/  04赛道 FOCUS 指标采集
│   └── tests/      单元测试
├── service/        Java 数据服务层 (Spring Boot, 封装脏接口为干净REST)
├── collector/      座位采集器 (Python纯标准库, 攒历史数据)
└── docs/           方案与文档
```

---

## 四、待实现清单

标记：★核心必做 · ☆扩展 · ○可选

### agent/ — Python Agent 层

**技术栈：Python 3.12 + FastAPI + openai SDK**

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `main.py` | FastAPI 入口：装配三功能单例 + 定义路由 (/findbook /seat /knowledge /memory /health) | FastAPI |
| ★ `config.py` | 从环境变量读配置 (SERVICE_BASE_URL / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL)；密钥绝不入库 | Python |
| ★ `service_client.py` | 异步调 Java 服务层：search_books / seats_now / health | httpx |
| `requirements.txt` | 依赖：fastapi, uvicorn, httpx, openai, pydantic, pytest, pytest-asyncio | — |
| `pytest.ini` | asyncio_mode=auto | pytest |
| `.env.example` | 团队配置模板 (密钥占位) | — |

### agent/core/ — 共享内核

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `llm.py` | LLMClient (兼容OpenAI协议) + Usage (token计量,04赛道成本指标) + available (判断key可用) + complete/complete_json | openai SDK |
| ★ `planner.py` | Planner.plan()：有key时用记忆精炼查询 (如"只要近五年"→年份约束)，无key/无记忆时原样透传；异常降级不打断主流程 | LLM |
| ★ `agent_loop.py` | AgentLoop：register_tool 注册工具；run()=检索记忆→规划(注入记忆)→调工具→组装结果(含耗时/token/记忆id/**trace_id**)；record_feedback()=**幂等**(按 user_id+反馈内容 hash 去重,防手快多点/网络重试重复入库)→抽取→冲突处理→入库 | Python |

### agent/memory/ — 反馈记忆核心 (护城河, 04赛道重点)

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `models.py` | MemoryType 枚举 (preference/rule/episode) + MemoryEntry (**user_id**(多用户隔离,趁数据少先加,后补是灾难)/type/subject/content/applies_to/confidence/source/dedup_hash(幂等去重)/created_at 时间戳(供衰减)) | Python dataclass + pydantic(校验) |
| ★ `store.py` | MemoryStore over SQLite：建表(**含 FTS5 虚拟表**) + add(带 dedup_hash 幂等) + query(**FTS5 全文检索**替代 LIKE + 按 user_id 隔离 + 适用范围过滤 + **时间衰减**:新记忆权重高,旧的按 created_at 衰减,"上周喜欢靠窗"不能永远压过"昨天喜欢靠门") + resolve_conflicts(同类矛盾旧记忆降权) + delete/all | SQLite + FTS5 |
| ★ `retriever.py` | MemoryRetriever：retrieve (**按 user_id 隔离** + top_k + 置信度阈值 + 衰减后综合得分 排序控token) + to_prompt_block (渲染成紧凑提示词块) | Python |
| ★ `extractor.py` | MemoryExtractor：用LLM把一句反馈抽取0-3条结构化记忆；**走 JSON mode + pydantic 校验**,不裸解析文本;**校验失败重试一次再丢弃**(别让解析残渣混进记忆库,洗都洗不干净);无key返回空,失败不打断 | LLM + pydantic |

### agent/features/ — 三个功能 (共享记忆闭环)

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `findbook/service.py` | P0找书：注册 search_books 工具(调Java层)，find() 走 agent 循环(query_key=query 走记忆注入, 透传 user_id + trace_id)，feedback() 幂等沉淀记忆 | httpx → Java 层 |
| ☆ `knowledge_map/semantic_scholar.py` | S2 Graph API 客户端：search / paper / references(展平citedPaper)，带 429 指数退避 | httpx |
| ☆ `knowledge_map/service.py` | P1知识地图：build_citation_graph 工具(接S2,无需LLM) + summarize_paper 工具(接LLM,按记忆的阅读风格生成摘要) | LLM + Semantic Scholar |
| ○ `seat_predict/service.py` | P2座位预测：predict_seats 工具，**先做笨基线**——同 weekday+同时段历史平均占用率排序推荐(稳、可解释、先上线顶着,日后还能当模型对照组),别急着上模型；读采集库连接设 busy_timeout；feedback() 纠错入记忆 | SQLite |

### agent/benchmark/ — 04赛道 FOCUS 指标

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ☆ `harness.py` | 采集单任务 token成本 / 延迟 / 记忆命中率 / 记忆误用率，聚合成可演示的指标面板 | Python |

### agent/tests/ — 单元测试

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ☆ `test_memory.py` | 记忆存取 / 置信度过滤 / 通配可见 / 冲突降权 / 提示词块渲染 | pytest |
| ☆ `test_planner.py` | 无key降级为透传 / 无记忆透传 / agent循环 query_key 行为 | pytest-asyncio |
| ○ `test_seat_predict.py` | 预测按占用率升序排序 / 占用率计算正确 | pytest-asyncio |

### service/ — Java 数据服务层

**技术栈：Java 21 + Spring Boot 3.3.5 + Maven**
职责：把混乱的 OPAC / 座位第三方接口封装成干净、稳定的内部 REST。agent 只跟它说话。

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `pom.xml` | Spring Boot 父POM + spring-web(**MVC, 用 RestClient 不用 WebClient/webflux**, 避免混栈藏 .block()) + spring-cache + caffeine | Maven |
| ★ `LibraryPatchApplication.java` | Spring Boot 入口 | Spring Boot |
| ★ `application.yml` | 数据源配置：OPAC/座位 base-url、超时、libid | YAML |
| ★ `opac/OpacClient.java` | OPAC 检索客户端(**RestClient** POST)，解析内嵌 holdings JSON；**重试分错误类型**:超时可重试、4xx 不重试、429/5xx 才退避(一股脑退避只会放大故障) | Spring RestClient |
| ★ `opac/Book.java` | 书目 DTO (title/author/isbn/publisher/pubYear/classNo/callNos/holdings) | Java record |
| ★ `opac/Holding.java` | 馆藏 DTO (callNo/location/status/available/barCode) | Java record |
| ☆ `seat/SeatClient.java` | 座位占用客户端(**RestClient** GET)，**强制按 GBK 解码**(别信响应头 charset,老 ASP 站点经常标错)，解析区域名的 x/y 占用 | Spring RestClient |
| ☆ `seat/SeatArea.java` | 区域占用 DTO (mapId/areaName/libCode/total/free/occupied) | Java record |
| ★ `web/BookController.java` | GET /api/books/search?q=&page=&pageSize=；透传/回传 trace_id | Spring MVC |
| ☆ `web/SeatController.java` | GET /api/seats/now；透传/回传 trace_id | Spring MVC |
| `env.sh` | 锁定 JAVA_HOME 到 Java 21 | Shell |
| ○ Java 单测 | OpacClient / SeatClient 解析测试 | JUnit |

### collector/ — 座位采集器

**技术栈：Python 纯标准库 (urllib + sqlite3)**
职责：座位系统无历史接口，靠它定时攒时间序列供 P2 预测。今天就该挂后台，靠时间攒数据。

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| ★ `seat_collector.py` | 定时抓区域级(GetSeatCount) + 单座级(GetSeatList)占用，**强制 GBK 解码**，存 SQLite(建库设 WAL)；once/loop 两种模式，循环里任何异常不中断；**抓取失败与"真没数据"必须分开存**(网络抖一下不能被模型当成"这个点没人",历史一旦污染洗不回来)；**时区写死 Asia/Shanghai** | Python 标准库 |

### docs/ — 文档

| 待建文件 | 要实现什么 | 技术栈 |
|---|---|---|
| `方案.md` | 整合方案 (P0/P1/P2 定位 + 十天排期 + 风险与砍单标准) | Markdown |
| ○ 分赛道包装材料 | 01/02/04 各一份演示材料 (临近提交时写) | Markdown |
| ○ 访谈记录 | 真实用户原话 (01赛道证据) | — |

---

## 五、横切关注点（比功能更容易翻车，别漏）

> 以下是跨多个文件的非功能需求。上面的清单只列了"功能文件"，这一节才是工程能不能立住的地方。

### 1. 两层之间的鉴权与容错

- **鉴权**：Java 服务层默认只绑 `127.0.0.1`，不主动暴露公网。若必须公网可达（远程演示），加内部 token：agent 请求带 `X-Internal-Token` 头，Java 侧过滤器校验，失败 401。token 走环境变量。
- **容错**：`service_client` 必须有 超时 + 有限重试 + 降级，不能裸调。Java 挂了时——找书返回明确错误提示（非 500 堆栈），座位可回退"直读采集库"。
- **待加**：`service/.../web/AuthFilter.java`（token 校验）；`service_client.py` 里的 retry/timeout/fallback 逻辑。

### 2. 缓存（OPAC 走 VPN 慢、S2 限流狠）

- **OPAC**：Java 侧对检索结果做 TTL 缓存（Caffeine + spring-cache），相同查询短期不重复打 OPAC。`pom.xml` 加 `spring-boot-starter-cache` + `caffeine`。
- **Semantic Scholar**：Python 侧对 paper/references 做**持久缓存**（引用关系稳定，存 SQLite 或 JSON 文件），显著降 429。
- **待加**：`service` 缓存配置（@Cacheable + Caffeine）；`knowledge_map/s2_cache.py`。

### 3. 采集器怎么常驻、挂了谁拉起

- `nohup` 只是"启动一次"，进程崩了没人管，不叫常驻。真常驻要进程守护 + 自动拉起：
  - macOS：**launchd**（plist 设 `KeepAlive=true`，崩溃自动重启，开机自启）
  - Linux：**systemd**（unit 设 `Restart=always`）
- **待加**：`collector/com.dlut.seatcollector.plist`（launchd 模板）或 systemd unit；README 写清安装/查看/停止命令。

### 4. SQLite 并发（采集器写 + 预测读同一个库）

- 采集器持续写 `seats.db`，P2 预测同时读——不开 WAL 迟早 `database is locked`。
- **必须**：建库即 `PRAGMA journal_mode=WAL`（持久设置，设一次即生效）+ 读写连接都设 `busy_timeout`（如 5000ms）。
- **待加**：`seat_collector.py` 建库时设 WAL；`seat_predict/service.py` 读连接设 busy_timeout。

### 5. 不可再生数据的备份

- `seats.db`（座位时间序列）和 `memory.db`（用户记忆）都是靠时间攒出来的，`.gitignore` 忽略后仓库里没有任何副本——一旦误删/损坏就永久丢失，且赛期无法重来。
- **首选 Litestream**：把 SQLite 持续同步到对象存储（S3/兼容），比定时 `cp`/`.backup` 靠谱——它是流式增量复制，崩溃点可恢复，几乎不丢数据。
- **退路**：没对象存储就定时 `sqlite3 .backup` 到带时间戳文件（另存目录或外部盘）。备份不进 git，但**必须有明确落盘位置**并在 README 写明。座位库尤其关键——只增不减且不可回补。

### 6. 用户入口（用户到底从哪儿用）★ 现在完全缺失

- 目前只有 REST API（agent :8000 / service :8080），**没有任何人能真正"用"这个产品**。演示时也需要一个可见入口。
- **方案**：`web/` 前端 —— Vue 3 + Vite + ECharts（对话式找书界面 / 知识地图关系图可视化 / 座位占用+指标面板）。无前端人力则降级用 **Streamlit** 快速出一个能演示的界面。
- **待建**：`web/` 目录（前端）。这是 P0 能否被"体验"的前提，别等到最后。

### 7. 反馈入环的幂等（防重复强化）

- 用户手快多点两下、或网络重试，同一条反馈会进两遍——记忆被重复强化，后面的冲突降权也被带歪。
- **必须**：`record_feedback` 幂等。按 `user_id + 反馈内容` 算 dedup_hash，入库前查重，命中即跳过。
- **待加**：`agent_loop.record_feedback` 的去重逻辑；`memory` 表 dedup_hash 字段 + 唯一索引。

### 8. 多用户隔离（趁数据少赶紧加）

- 若系统多人用，记忆必须按用户隔离——否则 A 的偏好污染 B 的结果。
- **趁现在数据少，加个 `user_id` 字段就行；等数据攒起来再改是灾难**（要洗历史数据 + 迁移）。
- **待加**：`MemoryEntry.user_id`；`store.query` / `retriever.retrieve` 全部按 user_id 过滤。

### 9. 跨层链路追踪（trace id）

- 排查"找书失败"时，若两边日志没有关联 id，只能肉眼对时间戳，极其痛苦。
- **必须**：agent 生成 trace_id，随请求头传给 Java 层，两边日志都打这个 id。
- **待加**：`service_client` 注入 `X-Trace-Id` 头；Java 侧过滤器读入并放进 MDC/日志。

---

## 六、数据源关键事实（踩坑备忘，实现时照此，别重新摸）

### OPAC 馆藏检索（需校园网/VPN）

- 接口：POST https://opac.lib.dlut.edu.cn/meta-local/opac/search/ （尾斜杠必须有）
- 请求体：page / pageSize / indexName=idx.opac，外加 queryFieldList 数组，元素为 logic=0、field=all、values=[关键词]
- 坑：必须用 queryFieldList 结构（field=all 为全字段检索），裸 q 会返回全库不过滤。
- 返回 data.dataList[]，单条含 title/author/isbn/publisher/pub_year/abstract/classno/callno，外加内嵌 holdings（是被转义的 JSON 字符串，需二次解析）。holdings 里有 callNo(索书号)、location(架位)、status(在馆状态，如"可借")、circStatus、barCode。
- 详情接口（bibs/{id} 系列）均 404，用不上；一个检索接口的字段就够。

### 座位系统（公网可达，无需 VPN）

- 供应商 360banke/晓图，base = https://www.360banke.com/xiaotu/，libid=dlut，**GBK 编码——强制按 GBK 解，别信响应头 charset（老 ASP 站点常标错）**。
- 区域级：GetSeatCount.asp?libid=dlut → maplist(楼层,含libcode) + maparea(区域, name 形如"301阅览室 143/143", ct=座位数)。
- 单座级：GetSeatList.asp?libid=dlut&mapid=楼层id → seats[]，每座含 seatid/mappos/isbusy/seattype(电源、台灯)/seatnum/status。
- 另有 SSE 实时流（seatlistsse/seatcountsse）。
- 系统无历史接口——预测所需历史数据只能靠采集器攒。

### Semantic Scholar（P1 数据源，免费，无 VPN）

- base = https://api.semanticscholar.org/graph/v1
- 搜索：GET /paper/search?query=&limit=&fields=paperId,title,year,abstract,authors
- 引用：GET /paper/{id}/references?limit=&fields=paperId,title,year → 返回项在 data[].citedPaper，需展平。
- 坑：公共端点限流狠(429)，必须指数退避 + 持久缓存（见横切关注点 §2）。

### 环境

- Java 21：/opt/homebrew/opt/openjdk@21（Spring Boot 3.x 稳定支持；系统默认 Java 11 跑不了）。
- Maven / conda 经 Homebrew 装。
- 注意：OPAC 检索走 VPN，GitHub 推送走代理，二者网络互斥，注意切换。

---

## 七、实现优先级（按"能拿名次"排序）

> ⚠️ 有几件事**必须在数据攒起来之前做**（改 schema/洗历史数据的代价随时间指数上升）：记忆表的 `user_id`(多用户隔离) + `dedup_hash`(幂等)、采集器"失败 vs 没数据"分开存、时区写死。这些排在功能之前。

0. **数据模型的一次性决策（最优先，别拖）** → 记忆表 user_id + dedup_hash 字段；采集器失败/空值分离 + 时区 Asia/Shanghai。趁数据少，一行字段的事；攒起来再改是灾难。
1. 配 LLM key → 点亮 planner / extractor / P1摘要（三处核心全靠它），extractor 走 JSON mode + pydantic 校验
2. P0 找书端到端 + 前端入口 → 让产品"能被体验"（含 web/ 最小界面）；反馈入环做幂等
3. 横切关注点 → WAL、Litestream 备份、采集器常驻、trace id，别等数据丢了/排查抓瞎才想起
4. benchmark 跑批 → 04赛道要的真实指标数字
5. 去图书馆访谈 → 01赛道要的"真实用户"证据
6. 鉴权/缓存/记忆衰减/分赛道材料 → 临近提交再补（衰减可后加，但检索先上 FTS5）

---

## C 角色（粘合侧）当前状态

- `agent/main.py`、`service_client.py`、三个 `features/*`、`benchmark/harness.py`、`web/` 已按接口契约实现并有测试覆盖。
- `main.py` 中 `from agent.core.agent_loop import AgentLoop` 依赖 B 交付，B 完成前 `main.py` 无法真正启动（`agent/tests/` 下的单测通过依赖注入/替身规避此限制，已验证业务逻辑正确）。
- `seat_predict/service.py` 假定 `seats.db` 存在表 `seat_snapshots(weekday, hour, area_name, occupied, total)`，此 schema 待与 A 确认；若字段不同，只需改 `agent/features/seat_predict/service.py` 中的一处 SQL。
