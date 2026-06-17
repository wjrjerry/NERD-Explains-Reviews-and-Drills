# 后端数据库并发/性能测试计划

> 目标：围绕当前 FastAPI + SQLAlchemy AsyncSession + PostgreSQL 后端，系统性验证所有会产生数据库并发读写、状态竞争、唯一约束冲突、批量落库和“先删后插”覆盖写入的功能模块。
>
> 代码阅读范围：`app/models`、`app/repositories`、`app/services`、`app/routers`、`tests/conftest.py`、`docker-compose.yml`。当前普通 pytest fixture 使用 `sqlite+aiosqlite`，正式并发压力基准必须使用 Docker/PostgreSQL 16 环境执行；SQLite 仅用于轻量回归和接口逻辑冒烟。

## 测试分层

| 层级 | 目的 | 建议工具 | 数据库 | 触发方式 | 结果产物 |
|---|---|---|---|---|---|
| L1 仓储并发单测 | 直接验证 repository/service 的事务、唯一约束、状态更新是否正确 | `pytest-asyncio` + `asyncio.gather` | SQLite 可跑，PostgreSQL 必跑 | 同进程多 session 并发 | 断言最终表数据一致性 |
| L2 API 并发集成测试 | 验证 FastAPI 依赖注入、认证、业务校验和数据库写入在并发下是否稳定 | `httpx.AsyncClient` / `pytest` | PostgreSQL | ASGI 或真实 `uvicorn` | HTTP 成功率、错误码分布、DB 校验 |
| L3 端到端压力测试 | 验证真实 API + PostgreSQL + Redis + Celery worker 的吞吐、延迟和锁等待 | Locust 或 k6 | PostgreSQL 16 | `docker-compose` 环境 | RPS、P95/P99、错误率、DB 指标 |
| L4 长稳/ soak 测试 | 发现连接泄漏、锁积压、后台任务堆积、表膨胀 | Locust/k6 + DB 监控 | PostgreSQL 16 | 30-120 分钟持续负载 | 趋势图、慢查询、锁等待报告 |

## 全局基准与观测项

| 类别 | 指标 | 建议阈值 | 采集方式 |
|---|---|---:|---|
| API 稳定性 | 非预期 5xx 错误率 | `< 0.1%` | HTTP 压测报告 |
| API 延迟 | 纯 DB 写接口 P95 | `< 300 ms` | Locust/k6 |
| API 延迟 | AI/mock 批量生成类接口 P95 | `< 1500 ms`，真实 LLM 单独标记 | Locust/k6 |
| DB 连接 | 连接池耗尽次数 | `0` | 应用日志、PostgreSQL `pg_stat_activity` |
| 锁等待 | `lock wait` / deadlock | deadlock 为 `0` | PostgreSQL 日志、`pg_locks` |
| 数据一致性 | 重复行、孤儿行、错计数 | `0` | 测后 SQL 校验 |
| 后台任务 | pending/running 卡住任务 | 测后 `0` 或符合 worker 并发上限 | `parse_tasks`、`knowledge_jobs` |
| 资源 | CPU/内存随时间持续上涨 | 不允许无界增长 | Docker stats / Prometheus |

## 核心并发测试矩阵

| ID | 模块 | 并发入口 | 关键数据库对象 | 并发模型 | 压测规模建议 | 必须断言 | 优先级 |
|---|---|---|---|---|---:|---|---|
| DB-C01 | 认证注册 | `POST /auth/register` | `users.username` 唯一约束 | 同一用户名并发注册 | 20/50/100 并发 | 只有 1 条用户记录；其他请求返回业务错误，不出现未捕获 `IntegrityError` 或 500 | P0 |
| DB-C02 | 登录审计 | `POST /auth/login` | `users.last_login_at` | 同一用户并发登录 | 100 并发，循环 5 轮 | 全部成功；`last_login_at` 为最近时间；无连接池耗尽 | P1 |
| DB-C03 | 用户状态管理 | `PATCH /admin/users/{id}/status` | `users.is_active` | 管理员并发启用/禁用同一用户 | 20 并发交替 true/false | 最终状态等于最后一次有序请求或允许最终一致；无脏写异常；普通用户权限不越权 | P1 |
| DB-C04 | 学习目标创建 | `POST /study-targets` | `study_targets` | 同一用户批量创建目标 | 100 并发 | 记录数准确；分页 total 准确；不同用户互不串数据 | P1 |
| DB-C05 | 学习目标更新/删除竞争 | `PATCH/DELETE /study-targets/{id}` | `study_targets.is_deleted` | 并发更新标题、软删除、读取详情 | 30 并发混合 | 删除后不可见；更新不会复活软删除记录；读接口返回一致错误码 | P1 |
| DB-C06 | 材料上传 | `POST /materials` | `materials.stored_filename` 唯一约束、`parse_tasks` | 同一用户/同一目标并发上传不同文件 | 50/100 并发 | materials 记录数等于成功数；stored_filename 不重复；auto_parse 时 parse_tasks 数量匹配 | P0 |
| DB-C07 | 材料重复解析入队 | `POST /materials/{id}/parse` | `materials.parse_status`、`parse_tasks` | 同一材料并发点击重新解析 | 20/50 并发 | 不产生无法解释的任务风暴；状态在 `parsing/running/succeeded/failed` 间合法；最新任务可查询 | P0 |
| DB-C08 | 材料删除与读取竞争 | `DELETE /materials/{id}` + `GET /materials/{id}` | `materials.is_deleted` | 删除、详情、预览、文件访问并发 | 30 并发混合 | 删除后 API 不再返回材料；并发读最多返回删除前快照或 404/业务错误；无 500 | P1 |
| DB-C09 | 解析任务状态机 | `ParserService` / `ParseTaskRepository` | `parse_tasks.task_status` | 多 worker 同时 mark_running/succeeded/failed/retry 同一任务 | 10/20 worker 模拟 | 不出现非法状态倒退；`retry_count` 不丢增；finished_at/started_at 合法 | P0 |
| DB-C10 | 结构化解析替换 | `MaterialStructureRepository.replace_for_material` | `material_sections/chunks/figures/tables/formulas` | 同一材料并发 replace，读 structured | 10/20 并发 | 最终结构来自一次完整写入；无半删半插可见；无孤儿 chunk/figure/table/formula | P0 |
| DB-C11 | 结构化内容读取 | `GET /materials/{id}/structured` 及分项接口 | material structure tables | replace 与多读并发 | 100 读 + 5 写 | 读请求无 500；响应内 section/chunk 引用一致；P95 可接受 | P1 |
| DB-C12 | 知识任务 dedupe | `POST /knowledge-jobs/graph-refresh` | `knowledge_jobs.dedupe_key` 唯一约束 | 同一 target/material 并发入队 | 20/50/100 并发 | 只有 1 条相同 dedupe_key 记录；并发请求返回同一 job 或合法 rerun；不能暴露 `IntegrityError` | P0 |
| DB-C13 | 知识任务运行/重跑 | `KnowledgeJobService.process_job_by_id` + enqueue | `knowledge_jobs.status/rerun_requested` | 运行中并发重新入队、成功后自动重跑 | 20 enqueue + 2 worker | running 时设置 rerun_requested；成功后重置 pending 并再次入队；状态链合法 | P0 |
| DB-C14 | 知识图谱全量替换 | `POST /knowledge-graphs/generate` force regenerate | `knowledge_points`、`user_knowledge_mastery`、`material_knowledge_points` | 同一 target 并发生成/替换 | 5/10 并发，mock LLM 固定输出 | 最终图谱完整；每个 point 有 mastery；无指向已删除 point 的关系 | P0 |
| DB-C15 | 知识图谱同步合并 | `KnowledgeGraphRepository.sync_graph_for_target` | `knowledge_points`、`material_knowledge_points` | 多请求增量生成相同/相近知识点 | 10 并发 | 规范化同名点不重复膨胀；物料 evidence 不丢失；parent_id 无自环 | P0 |
| DB-C16 | 知识点合并 | `merge_points_for_target` | point 关系表、review tasks、mastery | 并发合并同一批重复知识点 | 5/10 并发 | 关系迁移完整；唯一关系表无重复；mastery 计数合并正确；无死锁 | P0 |
| DB-C17 | 掌握度更新 | `PATCH /knowledge-points/{id}/mastery` | `user_knowledge_mastery` 唯一约束 | 同一知识点并发创建/更新 mastery | 20/50 并发 | 最终只有 1 条 mastery；更新字段合法；不因 get_or_create 竞态产生唯一约束 500 | P0 |
| DB-C18 | 问答记录 | `POST /qa/ask` | `qa_records`、`qa_knowledge_points`、AI log | 同一材料并发提问 | 50/100 并发 | qa_records 数量准确；知识点关联不重复；AI 用量日志数量准确 | P1 |
| DB-C19 | 题目生成 | `POST /questions/generate` | `questions`、`question_knowledge_points` | 同一材料/target 并发生成题目 | 20/50 并发 | 题目数量符合请求；关联表无重复；分页列表 total 准确 | P1 |
| DB-C20 | 测验提交 | `POST /tests/submit` | `test_records`、`test_answer_records`、`wrong_questions`、wrong links | 同一用户对同一题集并发提交 | 50/100 并发 | test_records 数量准确；answer_records 每次提交完整；wrong_questions 与错题数匹配；无孤儿记录 | P0 |
| DB-C21 | 错题掌握状态 | `PATCH /wrong-questions/{id}/mastery` | `wrong_questions.review_count/status` | 同一错题并发标记 mastered/reviewing/unmastered | 20/50 并发 | `review_count` 不丢增或明确按最后写入策略；时间字段合法；无状态越权 | P0 |
| DB-C22 | 错题复习队列 | `GET /wrong-questions/review-queue` + mastery 更新 | `wrong_questions`、wrong point links | 多读队列 + 多写状态 | 100 读 + 20 写 | 队列不返回越权数据；due_only 过滤正确；无重复异常放大 | P1 |
| DB-C23 | 复习计划生成 | `POST /review-plans/generate` | `review_plans`、`review_plan_tasks` | 同一 target 并发生成计划 | 20 并发 | 每个 plan 的 tasks 完整；无 orphan task；列表分页 total 准确 | P1 |
| DB-C24 | 复习任务完成状态 | `PATCH /review-plans/tasks/{id}` | `review_plan_tasks.completed` | 同一 task 并发完成/取消 | 50 并发交替 | 最终状态可解释；无 500；其他用户无法改写 | P1 |
| DB-C25 | AI 用量日志 | 所有 AI/mock 调用链 | `ai_call_logs` | QA、题目、图谱、复习计划混合并发 | 100 并发混合 | 日志条数与调用数一致；summary 聚合不超时；费用字段非负 | P1 |
| DB-C26 | 管理端列表查询 | `/admin/users/materials/tasks/logs` | 多表分页/聚合 | 写入高峰期间管理员分页查询 | 100 读 + 背景写 | total 准确或读已提交一致；P95 符合阈值；无慢查询异常 | P2 |
| DB-C27 | 导出接口 | `/exports/*.md/csv` | wrong/review/knowledge 多表读 | 写入高峰期间导出 | 20 并发导出 + 背景写 | 导出无 500；内容不含越权数据；大数据量下响应时间可接受 | P2 |
| DB-C28 | 健康检查 | `/health/db` | DB 连接池 | 压测期间持续探测 | 每秒 5 次，持续全程 | health 不因连接池饱和长期失败；失败时有可诊断日志 | P2 |

## 混合业务场景

| ID | 场景 | 用户路径 | 并发模型 | 数据校验 |
|---|---|---|---|---|
| FLOW-C01 | 新用户学习闭环 | 注册 -> 登录 -> 建目标 -> 上传材料 -> 解析 -> 生成题目 -> 提交测试 -> 查看错题 | 50 个独立用户同时执行 | 每个用户数据完全隔离；每个材料有对应 parse task；每次提交有完整 test/answer/wrong 记录 |
| FLOW-C02 | 同一课程高并发学习 | 1 个用户、1 个 target、多个材料和题目 | 100 虚拟用户共享同一账号 | 列表 total、分页、权限、状态更新稳定；目标下图谱/错题/计划引用一致 |
| FLOW-C03 | 后台任务高峰 | 批量上传材料并 auto_parse，同时触发 knowledge job | 50 上传 + 20 graph job + worker concurrency=2/4 | `parse_tasks` 和 `knowledge_jobs` 不长期卡住；dedupe 生效；worker 无重复消费同一 job |
| FLOW-C04 | 读多写少稳态 | 资料、图谱、错题、计划持续读取，偶发提交/解析 | 90% GET + 10% POST/PATCH，30-60 分钟 | P95/P99 稳定；DB 连接数稳定；无锁等待积压 |
| FLOW-C05 | 写入尖峰恢复 | 10 分钟内集中注册、上传、提交测试，然后降为读取 | 逐步升压 10/50/100/200 并发 | 尖峰后数据一致；后台任务清空；无内存/连接泄漏 |

## 建议测试数据规模

| 数据集 | 用途 | 用户数 | 目标数 | 材料数 | 知识点 | 题目 | 错题/提交 |
|---|---|---:|---:|---:|---:|---:|---:|
| small | CI 快速回归 | 5 | 10 | 20 | 100 | 300 | 100 |
| medium | PR 前并发验证 | 50 | 100 | 500 | 5,000 | 20,000 | 5,000 |
| large | 发布前压力基准 | 500 | 1,000 | 5,000 | 50,000 | 200,000 | 50,000 |

## 测后数据库一致性检查

| 检查项 | 示例 SQL/断言方向 |
|---|---|
| 用户唯一性 | `select username, count(*) from users group by username having count(*) > 1;` 必须为空 |
| 知识任务唯一性 | `select dedupe_key, count(*) from knowledge_jobs group by dedupe_key having count(*) > 1;` 必须为空 |
| mastery 唯一性 | `select user_id, target_id, knowledge_point_id, count(*) from user_knowledge_mastery group by 1,2,3 having count(*) > 1;` 必须为空 |
| 题目-知识点唯一关系 | `question_knowledge_points` 中 `(question_id, knowledge_point_id)` 无重复 |
| QA-知识点唯一关系 | `qa_knowledge_points` 中 `(qa_record_id, knowledge_point_id)` 无重复 |
| 错题-知识点唯一关系 | `wrong_question_knowledge_points` 中 `(wrong_question_id, knowledge_point_id)` 无重复 |
| 结构化材料孤儿数据 | chunks/figures/tables/formulas 的 `material_id` 必须存在于未删除或可追溯的 material；`section_id` 非空时必须存在 |
| 复习计划孤儿任务 | `review_plan_tasks.plan_id` 必须存在 |
| 测验提交完整性 | 每个 `test_records.total_count` 等于对应 `test_answer_records` 数量 |
| 错题生成完整性 | 每个提交的 `wrong_count` 与对应 wrong question 数量一致，除非业务明确允许重复错题累计 |
| 状态机合法性 | `parse_tasks`、`knowledge_jobs` 无长时间 `running` 且 `started_at` 为空的记录 |

## 实现建议

| 文件建议 | 内容 |
|---|---|
| `tests/test_db_concurrency_auth.py` | C01-C03，重点覆盖唯一约束和同一用户状态竞争 |
| `tests/test_db_concurrency_materials.py` | C06-C11，重点覆盖上传、解析任务、结构化 replace |
| `tests/test_db_concurrency_knowledge_jobs.py` | C12-C17，重点覆盖 dedupe、job 状态、图谱替换/同步/合并、mastery |
| `tests/test_db_concurrency_learning_flow.py` | C18-C24，重点覆盖 QA、题目、测验、错题、复习计划 |
| `tests/perf/locustfile.py` 或 `tests/perf/k6/*.js` | L3/L4 真实服务压力脚本 |
| `tests/perf/sql_consistency_checks.sql` | 测后 PostgreSQL 一致性检查脚本 |

## 执行顺序

| 阶段 | 命令/动作 | 通过标准 |
|---|---|---|
| 1 | 先补 P0 的 L1/L2 pytest 并发用例 | 本地 PostgreSQL 全绿，无 500，无一致性问题 |
| 2 | 使用 Docker 启动 `api/postgres/redis/worker` | health/db/redis 正常，worker 可消费任务 |
| 3 | 跑 medium 数据集压测 10-15 分钟 | 错误率、P95、DB 锁等待达标 |
| 4 | 跑 large 数据集或阶梯升压 | 找到吞吐上限和第一个瓶颈 |
| 5 | 跑 30-120 分钟 soak | 无资源泄漏、任务堆积、慢查询持续恶化 |

## 已识别高风险点

| 风险点 | 原因 | 对应测试 |
|---|---|---|
| `KnowledgeJobService.enqueue` 先查再插 | 并发下可能同时未查到同一 dedupe_key，依赖唯一约束兜底但服务层未显式处理 `IntegrityError` | DB-C12 |
| `KnowledgeGraphRepository.get_or_create_mastery` 先查再插 | 并发创建同一 mastery 可能触发唯一约束冲突 | DB-C17 |
| `MaterialStructureRepository.replace_for_material` 先删除再插入 | 并发 replace 或读写交错可能产生短暂空结构或最终半覆盖 | DB-C10/DB-C11 |
| `KnowledgeGraphRepository.replace_graph_for_target` 删除旧点后重建 | 并发图谱刷新可能导致引用迁移和 mastery/evidence 不一致 | DB-C14 |
| `ParseTaskRepository.reset_for_retry` 读改写 `retry_count` | 多请求重试可能丢增 | DB-C09 |
| `WrongQuestionRepository.update_mastery_status` 读改写 `review_count` | 并发复习可能丢失 review_count 增量 | DB-C21 |
| 测验提交批量写入多表 | `test_records`、`test_answer_records`、`wrong_questions` 分批 flush/commit，错误处理需保证不残留半成品 | DB-C20 |
| SQLite 与 PostgreSQL 并发语义不同 | SQLite 文件锁和隔离行为不能代表生产 | 所有 P0 需 PostgreSQL 复跑 |

