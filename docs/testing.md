# 测试综合文档

本文档面向测试执行、回归验收和课程报告编写，覆盖当前自动化测试体系、测试点、运行方式和注意事项。

## 1. 测试目标

测试目标包括：

1. 验证 AI 学习平台主业务闭环是否可运行。
2. 验证认证、权限、跨用户隔离和管理员能力。
3. 验证资料上传、解析、结构化结果和 AI 前置条件。
4. 验证知识提炼、知识图谱、问答、出题、自测、错题和复习计划。
5. 验证边界输入、分页参数、非法状态和错误响应。
6. 区分本地 mock AI 回归、Docker 集成测试和真实 AI 验收测试。

## 2. 测试环境

### 2.1 本地 pytest 环境

`tests/conftest.py` 会为大多数后端测试设置默认环境变量：

```text
DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=test-secret-key-do-not-use-in-production
CELERY_TASK_ALWAYS_EAGER=true
```

实际测试会创建临时 SQLite 文件并通过 `httpx.ASGITransport` 直接调用 FastAPI 应用，上传目录也会重定向到临时目录。因此大部分单元和接口测试不需要启动 Docker。

### 2.2 Docker 集成环境

`tests/integration_helpers.py` 面向真实运行中的后端服务，默认访问：

```text
TEST_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql+asyncpg://ai_study:ai_study_pwd@localhost:5432/ai_study_db
```

运行集成测试前应启动 Docker Compose 并完成数据库迁移。

### 2.3 真实 AI 验收环境

真实 AI 测试默认跳过。需要显式设置：

```text
RUN_REAL_AI_ACCEPTANCE=1
AI_PROVIDER=openai-compatible
AI_API_KEY=...
AI_BASE_URL=...
AI_MODEL=...
```

真实 AI 验收会产生外部网络调用和可能的费用，只在最终验收或供应商连通性排查时运行。

## 3. 测试分类

| 类别 | 代表文件 | 覆盖范围 |
| --- | --- | --- |
| 健康检查 | `test_health.py` | 根路径、数据库、Redis 健康接口 |
| 认证与安全 | `test_auth.py`, `test_security.py` | 注册登录、JWT、过期 token、错误 scheme、停用用户 |
| 前端边界契约 | `test_boundary_frontend.py` | 前端会遇到的非法输入、分页、权限和完整流程 |
| 资料模块 | `test_materials.py`, `test_integration_materials.py`, `test_member_a_core_flow.py` | 上传、解析、预览、删除、失败记录、类型和大小限制 |
| AI 闭环 | `test_ai_flow.py`, `test_integration_ai_learning_flow.py` | 知识提炼、QA、出题、自测、错题、复习计划 |
| 知识图谱 | `test_knowledge_graphs.py`, `test_knowledge_jobs.py`, `test_knowledge_mastery.py` | 图谱生成、增量合并、作业去重、掌握度 |
| 知识点 API | `test_knowledge_point_api_schemas.py`, `test_review_plan_knowledge_points.py` | 知识点关联资料/题目/错题，复习计划任务引用知识点 |
| QA 和出题范围 | `test_qa_target_scope.py`, `test_question_generation_scope.py` | 资料级、目标级、知识点聚焦 |
| 题目帮助 | `test_question_explain_api.py` | 提示、解析、追问和跨用户拒绝 |
| 错题复做 | `test_wrong_question_review.py` | 复习队列、复做状态、客观题本地评分 |
| OCR 和视觉解析 | `test_vision_parse_service.py`, `test_multimodal_parse_compare.py` | OCR/视觉结果合并、结构化块分类 |
| AI 用量 | `test_ai_usage.py` | token 费用估算配置 |
| 真实 AI | `test_real_ai_provider_smoke.py`, `test_real_ai_acceptance.py` | provider 连通性和真实模型闭环 |

## 4. 功能验证测试点

| 模块 | 测试点 |
| --- | --- |
| 用户认证 | 注册成功、重复用户名、登录成功、错误密码、不存在用户、当前用户读取 |
| Token 安全 | 未携带 token、无效 token、过期 token、非 Bearer scheme、停用用户 |
| 学习目标 | 创建、列表、详情、更新、删除、分页边界、跨用户访问拒绝 |
| 资料上传 | 空文件、缺失文件、缺失目标、目标不存在、跨用户目标、超大文件、非法类型 |
| 资料解析 | 上传后自动解析、手动重解析、解析状态流转、失败记录、解析文本预览 |
| 结构化内容 | sections、chunks、figures、tables、formulas、structured 响应形态 |
| AI 前置条件 | 未解析资料调用 QA/出题/自测返回冲突或错误 |
| 知识提炼 | 资料级、目标级、目标加资料增量刷新、最新提炼查询 |
| 知识图谱 | 生成图谱、空目标图谱、max_points 边界、节点掌握度字段、循环关系拒绝 |
| 知识作业 | 创建作业、读取作业、跨用户拒绝、重复 pending 作业合并 |
| QA | 资料级、目标级、知识点聚焦、空问题、历史分页 |
| 出题 | 题型合法性、数量边界、难度合法性、目标/资料范围 |
| 自测 | 空答案、非法 question_id、重复 question_id、客观题评分、主观题 AI 评分 |
| 错题 | 自动沉淀错题、列表筛选、掌握状态更新、跨用户拒绝、复做队列 |
| 复习计划 | 日期范围、非法日期、跨用户目标、任务完成状态更新 |
| 管理员 | 学生访问拒绝、管理员访问用户/资料/任务/日志、重试任务记录日志 |
| 导出 | 未登录拒绝、Markdown/CSV 文件响应 |
| AI 用量 | 未登录拒绝、列表分页、summary 统计 |

## 5. 边界测试点

边界测试主要集中在 `tests/test_boundary_frontend.py`，覆盖前端最容易触发的问题：

| 边界类型 | 示例 |
| --- | --- |
| 字段长度 | 空用户名、空密码、超长用户名、空目标标题 |
| 枚举值 | 非法目标类型、非法题型、非法难度、非法掌握状态 |
| 分页参数 | `page < 1`、`page_size` 超出范围 |
| 权限隔离 | 访问他人目标、资料、错题、管理员接口 |
| 状态冲突 | 未解析资料问答、未解析资料出题、解析失败后重试 |
| 文件边界 | 空文件、超大文件、不支持扩展名、缺失 multipart 字段 |
| 日期边界 | 复习计划结束日期早于开始日期、非法日期格式 |
| 响应契约 | public/protected/auth 接口统一 envelope，分页结构一致 |

## 6. 运行命令

### 6.1 运行后端主测试

在仓库根目录执行：

```bash
python -m pytest
```

如果使用 Docker 容器：

```bash
docker compose exec -T api python -m pytest
```

### 6.2 运行重点回归

```bash
python -m pytest tests/test_boundary_frontend.py tests/test_auth.py tests/test_security.py
```

资料和 AI 学习闭环：

```bash
python -m pytest tests/test_materials.py tests/test_ai_flow.py tests/test_knowledge_graphs.py
```

### 6.3 运行服务级集成测试

先启动服务：

```bash
docker compose up --build -d
docker compose exec -T api alembic upgrade heads
```

再运行：

```bash
python -m pytest tests/test_integration_smoke_auth_targets.py tests/test_integration_materials.py tests/test_integration_ai_learning_flow.py
```

如后端不在默认地址，设置：

```bash
TEST_BASE_URL=http://localhost:8000 python -m pytest tests/test_integration_smoke_auth_targets.py
```

### 6.4 运行真实 AI 测试

```bash
RUN_REAL_AI_ACCEPTANCE=1 \
AI_PROVIDER=openai-compatible \
AI_API_KEY=your_key \
AI_BASE_URL=https://example.com/v1 \
AI_MODEL=your_model \
python -m pytest tests/test_real_ai_provider_smoke.py tests/test_real_ai_acceptance.py
```

Windows PowerShell 示例：

```powershell
$env:RUN_REAL_AI_ACCEPTANCE="1"
$env:AI_PROVIDER="openai-compatible"
$env:AI_API_KEY="your_key"
$env:AI_BASE_URL="https://example.com/v1"
$env:AI_MODEL="your_model"
python -m pytest tests/test_real_ai_provider_smoke.py tests/test_real_ai_acceptance.py
```

## 7. 前端构建验证

前端当前没有独立测试框架，基本验证方式为 TypeScript 和 Vite 构建：

```bash
cd frontend
npm install
npm run build
```

该命令会先执行 `tsc -b`，再执行 `vite build`，可以发现类型错误、接口类型不匹配和打包错误。

## 8. 测试结论模板

课程报告或验收记录可按以下格式描述：

| 项目 | 结论 |
| --- | --- |
| 主业务闭环 | 已覆盖注册登录、目标、资料、解析、知识、问答、出题、自测、错题、复习计划 |
| 权限安全 | 已覆盖 JWT、角色权限、跨用户隔离和停用用户 |
| 资料处理 | 已覆盖 TXT/PDF/图片解析路径、失败记录和结构化结果 |
| AI 能力 | mock AI 可本地回归，真实 AI 测试可按需开启 |
| 前端联调 | 已覆盖前端会触发的主要边界输入和统一响应契约 |
| 待补充 | 后端尚未暴露 `GET /tests/records`，前端对应调用为预留能力 |

## 9. 测试维护注意事项

1. 新增模型时，在 `tests/conftest.py` 中导入模型模块，确保 `Base.metadata.create_all` 建表完整。
2. 新增接口时，应补充成功用例、未登录用例、跨用户用例和主要边界输入。
3. AI 相关测试优先使用 mock provider，真实 AI 测试必须显式开关。
4. 文件上传测试应使用临时目录，不要写入仓库固定路径。
5. 管理员测试可通过测试 helper 把普通用户提升为 admin，避免依赖固定账号。
6. 若修复或新增前端调用，优先在 `test_boundary_frontend.py` 增补对应契约测试。
