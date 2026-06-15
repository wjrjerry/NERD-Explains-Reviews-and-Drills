# AI 智能备考复习平台后端 Review 测试报告

## 1. 测试概述

本次 review 针对 `ai-study-backend` 后端项目进行集成测试设计、测试用例实现与实际执行验证。测试重点不是单个函数的局部正确性，而是验证 FastAPI 接口、PostgreSQL、Redis、文件上传存储、后台解析任务、AI 学习模块、错题本、复习计划和管理员功能之间的协作是否符合预期。

测试覆盖的核心业务闭环为：

```text
注册/登录
-> 创建课程/考试目标
-> 上传 TXT 资料
-> 后台解析资料
-> 知识提炼 / AI 问答 / AI 出题
-> 提交自测
-> 错题沉淀
-> 生成复习计划
```

同时覆盖未登录访问、跨用户资源隔离、非法文件、超大文件、未解析资料调用 AI、解析失败记录、管理员权限、解析任务重试和管理员日志等异常与权限场景。

## 2. 测试环境

| 项目 | 内容 |
|---|---|
| 项目路径 | `C:\Users\beidian\Desktop\SE\大作业\ai-study-backend` |
| 后端框架 | FastAPI |
| 数据库 | PostgreSQL |
| 缓存/依赖 | Redis |
| 容器编排 | Docker Compose |
| 测试框架 | pytest |
| 测试基础地址 | `http://localhost:8000` |
| 推荐 AI 配置 | `AI_PROVIDER=mock`，保证自动化结果稳定 |

测试启动命令：

```bash
docker compose up --build -d
docker compose exec api alembic upgrade heads
```

测试执行命令：

```bash
pytest -s -q \
  tests/test_integration_smoke_auth_targets.py \
  tests/test_integration_materials.py \
  tests/test_integration_ai_learning_flow.py \
  tests/test_integration_permissions_admin.py
```

## 3. 测试设计与实现

本次新增了完整的集成测试方案文档、测试辅助代码和 4 组 pytest 测试文件。

| 文件 | 作用 |
|---|---|
| `docs/integration-test-plan.md` | 集成测试方案，说明测试目标、范围、策略、用例和准出标准 |
| `docs/integration-test-result.md` | 集成测试执行过程记录，包含环境问题和复跑说明 |
| `tests/integration_helpers.py` | 集成测试公共辅助函数，包括注册登录、创建目标、上传资料、等待解析、管理员提升等 |
| `tests/test_integration_smoke_auth_targets.py` | 健康检查、认证、当前用户、复习目标和未登录访问测试 |
| `tests/test_integration_materials.py` | 资料上传、解析、预览、重解析、非法文件、超大文件、缺失目标和解析失败测试 |
| `tests/test_integration_ai_learning_flow.py` | 知识提炼、QA、QA 历史、AI 出题、自测、错题、复习计划测试 |
| `tests/test_integration_permissions_admin.py` | 跨用户隔离、管理员权限、任务重试和管理员日志测试 |

pytest 收集结果：

```text
tests/test_integration_ai_learning_flow.py: 3
tests/test_integration_materials.py: 6
tests/test_integration_permissions_admin.py: 2
tests/test_integration_smoke_auth_targets.py: 4
```

合计新增 15 条集成测试用例。

## 4. 测试用例汇总

| 编号 | 测试内容 | 覆盖点 | 最终结果 |
|---|---|---|---|
| IT-001 | 健康检查 | `/health`, `/health/db`, `/health/redis` | 通过 |
| IT-002 | 注册、登录、当前用户 | `/auth/register`, `/auth/login`, `/users/me` | 通过 |
| IT-003 | 复习目标 CRUD | 创建、列表、详情、更新、删除目标 | 通过 |
| IT-004 | 未登录访问 | 业务接口鉴权保护 | 通过 |
| IT-005 | TXT 资料上传解析 | 上传、后台解析、轮询状态 | 通过 |
| IT-006 | 资料预览与重解析 | TXT 预览、重新触发解析 | 通过 |
| IT-007 | 非法文件类型 | `.md` 文件上传被拒绝 | 通过 |
| IT-008 | 超大文件 | 超过 50MB 文件上传被拒绝 | 通过 |
| IT-009 | 缺失目标 ID | 不存在的 `target_id` 不产生孤立资料 | 通过 |
| IT-010 | 解析失败记录 | 缺失文件路径导致 `parse_status=failed` 并记录错误 | 通过 |
| IT-011 | 未解析资料调用 AI | QA、知识提炼、出题返回 409 | 通过 |
| IT-012 | 知识提炼与 QA | 知识提炼、问答、引用片段、QA 历史 | 通过 |
| IT-013 | AI 出题、自测与错题 | 出题、提交错误答案、错题沉淀、掌握状态更新 | 通过 |
| IT-014 | 复习计划 | 基于目标和错题生成复习计划并查询 | 通过 |
| IT-015 | 权限与管理员 | 跨用户隔离、学生访问 admin 被拒绝、管理员任务重试和日志 | 通过 |

## 5. 测试结论

本次后端集成测试共设计并执行 15 条自动化测试用例，覆盖健康检查、认证、复习目标、资料上传与解析、AI 学习闭环、自测评分、错题沉淀、复习计划、权限隔离和管理员功能。

最终测试结果全部通过，说明当前后端主要模块之间的接口协作、鉴权控制、数据持久化、后台解析任务和核心业务流程符合预期。

从 review 角度看，本次测试验证了以下关键质量点：

1. 基础服务可用：API、数据库、Redis 健康检查通过。
2. 用户身份链路可用：注册、登录、JWT 鉴权、当前用户查询正常。
3. 学习目标和资料模块可用：目标 CRUD、资料上传、解析、预览和删除流程正常。
4. AI 学习闭环可用：已解析资料可以完成知识提炼、QA、出题、自测、错题和复习计划流程。
5. 异常处理可用：非法文件、超大文件、解析失败、未解析资料调用 AI 等场景能返回明确错误。
6. 权限隔离有效：未登录访问、跨用户资源访问、学生访问管理员接口均被限制。
7. 管理员功能可用：管理员可以查询用户、资料、解析任务，并可重试解析任务和查看操作日志。

## 7. 遗留风险与建议

1. 当前自动化测试建议使用 `AI_PROVIDER=mock`，主要验证业务流程和响应结构；真实大模型输出质量仍建议通过人工验收或单独的端到端测试补充。
2. 目前测试重点是功能集成正确性，尚未覆盖并发上传、长文件解析、大量错题数据和高并发问答等性能场景。
3. 建议后续将这 15 条集成测试纳入 CI 或每次提交前的回归测试流程。
4. 若后续接入 PDF/OCR 和图片解析能力，应新增 PDF、扫描件和图片资料的解析集成测试。
5. 若真实 AI Provider 作为交付范围，应增加一组可选测试，只断言结构和非空字段，不断言具体文本内容。

## 8. Review 结论

本次 review 认为：后端当前核心功能已经具备较完整的自动化集成测试覆盖，且在 Docker Compose 环境修复后 15 条集成测试全部通过。项目可以进入下一阶段前后端联调、演示验收或进一步扩展测试。
