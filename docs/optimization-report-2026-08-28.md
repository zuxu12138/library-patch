# 优化与合并执行报告（2026-08-28)

> 背景:仓库三个角色的实现分散在两条分叉分支上——`main`(A 角色 Java service/collector + B 角色 agent core/memory)与 `feature/add-role-progress-clean`(C 角色 web/features/main.py)。本轮完成合并、打通、全链路优化与 UI 重做,并由 Claude Code 执行验证。
> 执行环境:Windows 11 + JDK 21 + Python 3.13 venv(蓝图原定 conda+3.12,本机无 conda,以 venv + requirements.txt 锁定版本代替)。

---

## 一、分支合并与接口打通

三方代码在没有任何一方见过其他方实现的情况下写成,合并后暴露出 4 个接口错位:

| 问题 | 现象 | 修法 |
|---|---|---|
| AgentLoop 装配 | C 按 `AgentLoop()` 无参调用,B 实际需要 `(retriever, planner, store, extractor)` | `main.py` 补全装配,新增 `MEMORY_DB_PATH` 配置 |
| 工具调用契约 | B 的循环调 `handler(tool_args)`(单 dict),C 的四个工具与 FakeAgentLoop 全按 kwargs 写 | 统一为 dict 契约,fakes 与真循环行为对齐 |
| 座位表结构 | C 假定的 `seat_snapshots(weekday, hour, ...)` 不存在 | SQL 对齐 A 的真实表 `area_snapshot`,小时从 `hhmm` 前两位提取 |
| CORS 缺失 | web(:5173)直连 agent(:8000)被浏览器拦截 | `main.py` 加 CORSMiddleware |

合并提交: `954c9f4` + 修复提交 `8664543`。

---

## 二、稳定性修复(演示保命级)

### 1. 失败语义:不再把故障伪装成空结果
- **缓存空结果 bug**:`OpacClient.search()` 原来 catch 一切返回空 List,而方法挂着 `@Cacheable`——OPAC/VPN 挂掉时,**空结果会被 Caffeine 缓存 5 分钟**,恢复后用户看到的仍是空。现改为抛 `OpacException`(异常不进缓存),控制器转成 `50001` 信封。
- `SeatClient.areaOccupancy()` 同理改抛 `SeatException`——座位系统挂掉不再被当成"全校空无一人"。
- 前端 `client.ts` 错误码映射为图书馆语境文案(「书架暂时清点中,请稍后再来」等),用户永远看不到堆栈。

### 2. 分页修复
`BookController` 原来返回 `total = books.size()`(当前页条数)。实测 OPAC 响应有真实 `total`/`actualTotal` 字段,现解析透出(实测 `total: 6780`),前端分页可用。

### 3. 超时配置接线(隐藏 bug)
`application.yml` 里配了 `timeout-ms: 15000/10000`,但两个 `RestClient` 构建时**从未读取**——OPAC 卡死会无限挂起。现已接线到 `SimpleClientHttpRequestFactory`。

### 4. S2 限流降级
`/knowledge/summarize` 原来在 S2 429 重试耗尽后裸抛异常 → 前端 500。现降级返回 `{"error": "..."}`,前端走正常空态。

### 5. 熔断器
`service_client` 连续失败 3 次熔断 30s,冷却期内直接 `ServiceUnavailable`,不让每个请求都等满超时放大故障;业务错误(4xx/信封错误码)不计入熔断。

---

## 三、记忆系统(护城河)修复

| 项 | 原来 | 现在 |
|---|---|---|
| 相关性检索 | `agent_loop` 不传 `query_text`,FTS5 索引实际从未被用到,每次拉全部记忆 | query_text **提权不扼杀**——FTS 命中排前,无字面重合的偏好(如"只看近五年")仍保留进 top_k |
| 冲突降权 | 同 (user,type,subject) 全部 ×0.5 连坐,"喜欢靠窗"和"喜欢安静"互相误伤 | extractor 提示词带已有记忆,LLM **点名** `contradicts` 数组,只降被点名的(`store.adjust_confidence`) |
| 反馈诚实 | 无 LLM key 时返回空 memory_ids 却显示"已记录" | 响应带 `llm_available`,前端诚实提示"本次不会被记住" |

## 四、座位预测:从"摆设"到可用

- **冷启动修复**:历史采样 <4 点时自动加大实时 `free` 权重,完全无历史时纯按实时空闲排序(原来 ranking 全是 0.0 平手)。
- **实时数据真正参与**:原来 `seats_now()` 查了只标个布尔;现在融合进排序分数,并透出 `free_now/total/samples/map_id/lib_code`。
- **楼层平面图**:打通 GetSeatList 单座级接口(GBK、mappos 坐标),新增 `/api/seats/map`(Java)→ `/seat/map`(agent)→ 前端 SVG 座位平面图(空闲/占用/电源角标)。

## 五、采集器限流器(★ 保留,勿删)

`collector/seat_collector.py` 顶部的限流器**保留**:

```python
COLLECT_OPEN_HOURS = (7, 23)   # 只在开馆时段采集
SEAT_EVERY_N_TICKS = 3         # 单座级每 3 个 tick 才采一次
```

**为什么保留**:单座级一次 15 层请求,5 分钟一轮全量时 2.5 小时就攒了 19 万行;开馆时段外数据对预测无价值。限流后单座数据量降为 1/3、夜间静默、对第三方接口更友好。

**以后要全量采集时**:把 `SEAT_EVERY_N_TICKS` 改为 `1`、`COLLECT_OPEN_HOURS` 改为 `(0, 24)` 即可;`once` 手动模式本来就不受限制器约束。

## 六、UI 重做(Editorial Minimalism)

- **设计系统**:Tailwind v4 + 自托管字体(Fraunces/Inter/JetBrains Mono/Noto Serif SC);米白纸底 #FAFAF7、深青 #0F5C5C 主色、赭红 #B3413C 仅角标;1px 分割线、无投影无渐变、`prefers-reduced-motion` 支持。
- **找书**:命令式搜索(⌘K/`/` 聚焦、Esc 清空、↑↓ 联想、最近检索 localStorage),编目卡打孔,hover 抽书,holdings 翻牌展开,真实分页,`plan_note` 偏好提示条。
- **座位**:星期 tab + 24h 滑杆(300ms 防抖),展签式排名,平面图下钻,分馆筛选,全馆空位汇总,置信度提示,历史-only 横幅。
- **知识地图**:制图学隐喻(图纸框/罗盘/图例/坐标钉/虚线航路),点击下钻,移动端退化列表,关键词找论文入口(新路由 `/knowledge/search`),摘要逐段浮现 + 作者胶片条 + PDF 印章。
- **全局**:启动 splash(900ms)、顶部「翻阅中」进度细线(axios 拦截器驱动)、墨点 FAB + 撕边便签纸反馈。
- **性能**:ECharts 按需引入 + 独立 chunk(1031KB → 501KB)。

## 七、运维与兜底

- `ops/backup.py`:SQLite 在线备份 + 轮转(替代 Litestream,本机无对象存储)。
- `collector/aggregation.py`:`area_hourly` 聚合 + 90 天原始数据 TTL。
- `scripts/start-all.ps1` / `.sh`:一键起四层(service/agent/collector/web)。
- `scripts/mock_service.py` + `docs/fixtures/`:演示现场 OPAC/VPN 不通时的兜底 mock(录制的真实响应)。
- `docs/api-samples.md`:四接口真实响应样例 + 字段设计要点(供 UI 设计参考)。

## 八、验证结果

| 层 | 结果 |
|---|---|
| Java | 编译通过;JUnit 8 例全过(OpacClient/SeatClient 解析,含 mappos) |
| Agent | pytest **77 例全过**(含新增:熔断/记忆提权/精准降权/S2 降级) |
| Web | `vue-tsc` 类型检查 + vite 构建通过 |
| 端到端 | 找书(真实 OPAC,total 6780)、座位预测(实时融合+平面图)、引用图、反馈幂等全部实测 |

## 九、已知遗留(明确不做/待做)

- LLM 相关(查询精炼/记忆抽取/摘要)待配 `LLM_API_KEY` 点亮,代码已就绪,降级路径已验证。
- docker-compose、CI 未做(部署环境未定)。
- S2 公共端点限流狠,演示前对要用的 paperId 先跑一遍让 `S2Cache` 落盘。
- 座位平面图为楼层粒度:同楼层不同区域点开是同一层全部座位(数据源粒度如此,非 bug)。
