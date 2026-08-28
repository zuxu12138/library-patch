# 后续优化工作规划

> **状态更新 (2026-08-28)**: 第一版已落地,Phase 0-3 大部分已由 Claude Code 执行完毕,详见 docs/optimization-report-2026-08-28.md。剩余: docker-compose/CI(Phase 4)、赛道材料(Phase 5)。

> 本文档用于：等其他开发者按 `README.md` 蓝图完成第一版实现后，由优化方（Claude Code）接手进行系统性打磨。
> 当前状态：仓库仍为蓝图阶段，各目录为空。

---

## 一、优化总原则

1. **先验收，再优化**：不直接改代码，先跑通、先看懂、先记录问题。
2. **稳定性 > 性能 > 演示效果**：老系统、VPN、LLM key 都是不可控外部依赖，优先让系统在恶劣条件下也能给出友好响应。
3. **数据是核心资产**：`memory.db` 和 `seats.db` 一旦污染很难清洗，所有优化以不损坏历史数据为前提。
4. **可观测性优先**：没 trace id 和统一错误码，演示时出问题只能两眼一抹黑。
5. **MVP 意识**：如果时间和人力紧张，优先保 P0 找书端到端可演示，P1/P2 可以降级。

---

## 二、优化阶段与任务

### Phase 0：接手验收（1 天）

目标：确认第一版实现是否达到「可优化」的基线。

| 验收项 | 检查点 | 不通过时的处理 |
|---|---|---|
| 目录结构 | 是否按 `agent/` / `service/` / `collector/` / `web/` / `docs/` 放置 | 先整理结构再优化 |
| 必做文件 | README 中所有 ★ 项是否已实现 | 列出缺失项，与开发方确认 |
| 环境隔离 | 密钥、URL、libid 是否走环境变量；`.env.example` 是否存在 | 如有 hardcode，先剥离 |
| 一次跑通 | `docker-compose up` 或等效命令能否启动全部服务 | 先解决启动阻塞 |
| P0 演示 | 用 curl/前端完成一次找书：输入 → 结果 → 反馈入库 | 不能跑通则先修主链路 |
| 横切关注点 | WAL、busy_timeout、幂等去重、user_id 隔离是否已落地 | 这些是 schema 级，优先补 |
| 数据安全 | `.gitignore` 是否排除了 `*.db`、`.env`、密钥文件 | 防止误提交 |

**交付物**：`acceptance-report.md`（问题清单 + 优先级）

---

### Phase 1：稳定性与健壮性（2-3 天）

目标：外网抖、VPN 断、LLM 慢、Java 挂时，系统都不崩溃。

#### 1.1 统一错误模型
- 定义跨层统一错误 JSON：
  ```json
  {
    "trace_id": "uuid",
    "error_code": "OPAC_TIMEOUT | S2_RATE_LIMIT | MEMORY_DEDUP | SEAT_FALLBACK | ...",
    "user_message": "面向用户的简短说明",
    "retryable": true,
    "detail": "内部调试信息，可选"
  }
  ```
- Python agent 侧所有异常都包装成该模型。
- Java service 侧返回的 HTTP body 也遵循同一模型。

#### 1.2 全链路 trace id
- 检查 `service_client.py` 是否在请求头注入 `X-Trace-Id`。
- 检查 Java 侧是否读取该头并写入 MDC / 日志。
- 确保 trace_id 贯穿：前端 → agent → Java → OPAC/座位/S2 → 返回。

#### 1.3 重试、退避、降级、熔断
- `service_client.py`：调 Java 层加 timeout + 有限重试 + 指数退避。
- Java `OpacClient`：4xx 不重试、429/5xx/超时退避重试。
- 加简单熔断：连续失败 N 次后，短时间直接返回降级信息，避免放大故障。
- LLM 不可用时完整降级：planner 透传、extractor 规则提取、摘要返回原文片段。
- P2 座位预测：Java 不可用时直读采集库，并明确标注数据来源。

**交付物**：稳定性改造后的 agent/service，附带一份降级场景测试用例。

---

### Phase 2：数据与存储质量（2 天）

目标：`memory.db` 和 `seats.db` 不丢、不锁、不被污染。

#### 2.1 SQLite 并发与 WAL
- 验证两个库建库时都执行 `PRAGMA journal_mode=WAL`。
- 所有读写连接统一设 `busy_timeout=5000`。
- 测试采集器持续写 + 预测读同一库的场景。

#### 2.2 采集数据质量控制
- 采集器记录：HTTP 状态码、响应耗时、解析异常。
- 落表时区分：
  - `fetch_failed`：网络/解析失败
  - `empty_data`：接口返回正常但无数据
  - `normal`：正常数据
- 对异常值标记脏数据：如 `free > total`、占用率为负、时间戳异常。

#### 2.3 备份与归档
- 配置 Litestream 持续同步到对象存储，并给配置示例。
- 演练一次从对象存储恢复。
- 无对象存储时，定时 `sqlite3 .backup` 到带时间戳文件。
- 座位原始数据 TTL 90 天，聚合后数据长期保留。
- 记忆库按 confidence + 年龄衰减，极低置信度可归档或清理。

**交付物**：`ops/backup.sh`、`collector/aggregation.py`、数据质量校验脚本。

---

### Phase 3：性能与成本（2 天）

目标：让系统快、LLM 调用少、演示不卡。

#### 3.1 缓存调优
- Java 侧验证 OPAC Caffeine 缓存生效，相同查询短期不重复打 VPN。
- Python 侧 Semantic Scholar 加持久缓存（SQLite/JSON），引用关系稳定可长期缓存。
- 给缓存加命中率监控。

#### 3.2 记忆检索优化
- 检查 `store.query` 使用 FTS5 而非 LIKE。
- 确认按 `user_id` 隔离、按适用范围过滤、按时间衰减排序。
- `retriever` 控制 token，避免一次性塞入过多记忆导致 LLM 成本飙升。

#### 3.3 Benchmark
- 完善 `agent/benchmark/harness.py`：
  - 单次请求 token 成本
  - 端到端延迟
  - 记忆命中率
  - 记忆误用率（检索到了但没用上 / 用上了但帮倒忙）
- 输出可导入 ECharts/Streamlit 的指标 JSON。

**交付物**：benchmark 报告、缓存命中率面板。

---

### Phase 4：工程化（2-3 天）

目标：让项目可交付、可复现、可维护。

#### 4.1 容器化
- 补 `docker-compose.yml`：agent / service / collector 一键启动。
- agent 和 service 使用固定环境变量，避免本地配置漂移。
- collector 以守护模式运行，崩溃自动重启。

#### 4.2 测试
- Python 单测：`test_memory.py`、`test_planner.py`、`test_seat_predict.py`。
- Java 单测：`OpacClientTest`、`SeatClientTest`（重点测解析）。
- 用 VCR / fixtures 录制 OPAC/座位真实响应，测试不依赖外网/VPN。

#### 4.3 CI / Lint
- 加 GitHub Actions 或本地脚本跑：
  - Python：ruff / black / pytest
  - Java：mvn test
- 确保提交前能快速发现回归。

#### 4.4 文档
- 把 README 拆分：
  - `README.md`：项目介绍 + 5 分钟启动
  - `docs/deployment.md`：部署、环境变量、备份恢复
  - `docs/development.md`：本地开发、测试、贡献指南
  - `docs/api.md`：REST API 契约

**交付物**：docker-compose、测试套件、CI 配置、拆分后的文档。

---

### Phase 5：演示与产品化（1-2 天）

目标：让评委和用户一眼看懂价值。

#### 5.1 用户入口
- 确认 `web/` 可用；无前端人力时用 Streamlit 兜底。
- 至少实现：对话式找书界面、知识地图关系图、座位占用面板。

#### 5.2 演示脚本
- 准备 3 分钟演示脚本：
  - 用户说「我想找近五年关于深度学习的书，不要太老的」
  - Agent 调用记忆 → 精炼查询 → 返回结果 → 用户点反馈
  - 切换到知识地图：展示某篇论文的引用网络
  - 切换到座位：推荐今日适合楼层

#### 5.3 赛道材料
- 01 赛道：用户访谈记录、使用场景、价值证明。
- 02 赛道：技术架构图、关键代码亮点、性能指标。
- 04 赛道：benchmark 数据、token 成本、记忆命中率、延迟。

#### 5.4 Dry Run
- 完整走一遍：启动 → 找书 → 反馈 → 知识地图 → 座位 → 收尾。
- 记录卡点并修复。

**交付物**：演示脚本、赛道材料、dry-run 问题清单。

---

## 三、风险与砍单标准

| 风险 | 应对 |
|---|---|
| LLM key 现场不可用 | 必须有 LLM-less 降级，P0 至少能原样检索 |
| OPAC/VPN 现场不通 | 准备录制好的响应 fixtures，演示时走 mock |
| 座位接口 429/改版 | 采集器直读 + 历史数据兜底 |
| 数据库损坏 | Litestream 备份 + 本地冷备双保险 |
| 时间不够 | 只保 P0 + Streamlit 前端，P1/P2 降级为截图/mock |

---

## 四、建议的优化顺序

```
Phase 0 接手验收
    ↓
Phase 1 稳定性（错误模型 + trace + 降级熔断）
    ↓
Phase 2 数据质量（WAL + 采集质控 + 备份）
    ↓
Phase 3 性能成本（缓存 + 检索 + benchmark）
    ↓
Phase 4 工程化（Docker + 测试 + CI + 文档）
    ↓
Phase 5 演示产品化（前端 + 脚本 + 材料）
```

**关键原则**：不要五个阶段并行。先让系统「稳」，再让它「快」，最后才是「好看」。

---

## 五、需要开发方在第一版中预留的接口

为了优化方能顺利接手，建议开发方在第一版中：

1. 所有跨层 HTTP 调用都预留 `timeout`、`retry`、`headers` 扩展参数。
2. 记忆模块暴露 `MemoryStore.add/query/delete/all` 四个方法，方便后续换存储。
3. agent 启动时打印配置摘要（隐藏 key），方便验收时核对。
4. service 提供 `/health` 和 `/ready` 端点，供 docker-compose healthcheck 使用。
5. 采集器支持 `--once` 和 `--loop` 两种模式，并暴露采集状态日志。

---

*规划时间：2026-08-24*
*适用范围：library-patch-blueprint 第一版实现完成后*
