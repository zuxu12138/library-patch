# 优化工作规划（接手后执行）

> 适用场景：其他开发者按 `README.md` 蓝图完成第一版后，由 Claude Code 接手做系统性优化。
> 当前仓库状态：仍为蓝图阶段，`agent/` `service/` `collector/` `web/` 均为空。

---

## 一、总原则

1. **先验收，再优化** —— 不直接改代码，先跑通、先看懂、先记录问题。
2. **稳定性 > 性能 > 演示效果** —— VPN / OPAC / LLM / 座位接口都是不稳定外部依赖，先保证恶劣条件下也能友好响应。
3. **数据是核心资产** —— `memory.db`、`seats.db` 一旦污染很难清洗，一切优化以不损坏历史数据为前提。
4. **可观测性优先** —— 没有 trace id 和统一错误码，出问题只能两眼一抹黑。
5. **MVP 保 P0** —— 时间不够时，P1 知识地图 / P2 座位预测可降级，P0 找书必须端到端可用。

---

## 二、优化阶段

### Phase 0：接手验收（1 天）

目标：确认第一版达到「可优化」基线，产出问题清单。

| 验收项 | 检查点 | 不通过的处理 |
|---|---|---|
| 目录结构 | 是否按 `agent/` `service/` `collector/` `web/` `docs/` 放置 | 先整理结构 |
| 必做文件 | README 中所有 ★ 项是否实现 | 列缺失项，与开发方确认 |
| 环境隔离 | 密钥/URL/libid 走环境变量；有 `.env.example` | 有 hardcode 先剥离 |
| 一次跑通 | `docker-compose up` 或等效命令能启动全部服务 | 先解决启动阻塞 |
| P0 演示 | 完成一次找书：输入 → 结果 → 反馈入库 | 先修主链路 |
| 横切关注点 | WAL / busy_timeout / 幂等去重 / user_id 隔离已落地 | 这些是 schema 级，优先补 |
| 数据安全 | `.gitignore` 排除 `*.db` `.env` 密钥文件 | 防误提交 |

**交付物**：`docs/acceptance-report.md`（问题清单 + 优先级）

---

### Phase 1：稳定性与健壮性（2-3 天）

#### 1.1 统一错误模型
```json
{
  "trace_id": "uuid",
  "error_code": "OPAC_TIMEOUT | S2_RATE_LIMIT | MEMORY_DEDUP | SEAT_FALLBACK | ...",
  "user_message": "面向用户的简短说明",
  "retryable": true,
  "detail": "内部调试信息，可选"
}
```
- agent / service 两侧都包装成该模型，用户看到的不是堆栈。

#### 1.2 全链路 trace id
- `service_client.py` 注入 `X-Trace-Id`，Java 侧读入并写 MDC/日志。
- 贯穿：前端 → agent → Java → OPAC/座位/S2 → 返回。

#### 1.3 重试 / 退避 / 降级 / 熔断
- agent 调 Java：timeout + 有限重试 + 指数退避。
- Java `OpacClient`：4xx 不重试、429/5xx/超时退避重试。
- 简单熔断：连续失败 N 次后短时间直接降级，不放大故障。
- LLM 不可用降级：planner 透传、extractor 规则提取、摘要返回原文片段。
- P2 座位：Java 不可用时直读采集库并标注来源。

**交付物**：稳定性改造 + 降级场景测试用例

---

### Phase 2：数据与存储质量（2 天）

- **WAL + busy_timeout**：两个库建库即 `PRAGMA journal_mode=WAL`，读写连接统一 `busy_timeout=5000`。
- **采集质控**：记录 HTTP 状态码 / 耗时 / 解析异常；区分 `fetch_failed`（网络/解析失败）、`empty_data`（正常但无数据）、`normal`。
- **脏数据标记**：`free > total`、占用率为负、时间戳异常等标脏。
- **备份**：Litestream 持续同步 + 演练恢复；无对象存储则定时 `sqlite3 .backup` 到时间戳文件。
- **归档**：座位原始数据 TTL 90 天、聚合数据长期保留；记忆按 confidence + 年龄衰减。

**交付物**：`ops/backup.sh`、`collector/aggregation.py`、数据质控脚本

---

### Phase 3：性能与成本（2 天）

- **缓存**：验证 OPAC Caffeine 缓存生效；S2 加持久缓存（引用关系稳定）。
- **记忆检索**：`store.query` 用 FTS5 而非 LIKE；按 user_id 隔离；`retriever` 控制 token。
- **Benchmark**：token 成本 / 端到端延迟 / 记忆命中率 / 记忆误用率，输出可演示 JSON。

**交付物**：benchmark 报告、缓存命中率面板

---

### Phase 4：工程化（2-3 天）

- **容器化**：`docker-compose.yml`（agent / service / collector 一键起，固定环境变量）。
- **测试**：pytest（memory / planner / seat_predict）+ JUnit（OpacClient / SeatClient 解析），用 VCR/fixtures 避免依赖外网。
- **CI/Lint**：ruff/black/pytest + mvn test。
- **文档**：拆分 README → `deployment.md` / `development.md` / `api.md`。

**交付物**：docker-compose、测试套件、CI 配置、拆分文档

---

### Phase 5：演示与产品化（1-2 天）

- **入口**：`web/` 可用，无人力则 Streamlit 兜底（对话找书 / 知识地图关系图 / 座位面板）。
- **脚本**：3 分钟演示（模糊找书 → 反馈 → 引用网络 → 座位推荐）。
- **赛道材料**：01 用户证据 / 02 技术亮点 / 04 指标数据。
- **Dry run**：完整走一遍，记录卡点并修复。

**交付物**：演示脚本、赛道材料、dry-run 问题清单

---

## 三、风险与砍单标准

| 风险 | 应对 |
|---|---|
| LLM key 现场不可用 | LLM-less 降级，P0 至少能原样检索 |
| OPAC/VPN 现场不通 | 录制响应 fixtures，演示走 mock |
| 座位接口 429/改版 | 采集器直读 + 历史数据兜底 |
| 数据库损坏 | Litestream + 本地冷备双保险 |
| 时间不够 | 只保 P0 + Streamlit 前端 |

---

## 四、优化顺序

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

**关键：不要五个阶段并行。先稳 → 再快 → 最后好看。**

---

## 五、需要开发方第一版预留的接口

1. 跨层 HTTP 调用预留 `timeout` / `retry` / `headers` 扩展参数。
2. 记忆模块暴露 `MemoryStore.add/query/delete/all`，方便换存储。
3. agent 启动打印配置摘要（隐藏 key）。
4. service 提供 `/health`、`/ready` 供 healthcheck。
5. 采集器支持 `--once` / `--loop`，暴露采集状态日志。

---

*规划时间：2026-08-24 · 待第一版实现完成后执行*
