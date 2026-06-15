# 后端开发分工方案

## 1. 当前仓库情况

当前后端仓库是一个基于 FastAPI 的初始骨架，已经具备基础运行环境：

- `app/main.py`：FastAPI 应用入口和路由注册。
- `app/core/config.py`：环境变量与系统配置。
- `app/db/session.py`：异步 SQLAlchemy 数据库连接。
- `app/routers/health.py`：健康检查接口。
- `docker-compose.yml`：API、PostgreSQL、Redis 编排配置。
- `requirements.txt`：Python 依赖列表。

目前业务模块尚未展开，因此适合在开发前先约定目录结构、模块边界和接口风格，再由三名成员并行推进。分工目标是保证职责清晰、文件边界明确、合并冲突尽量少。

## 2. 分工原则

本项目后端由两名成员负责编码开发，一名成员负责测试与验收。整体按照“资料入口与平台基础”和“AI 学习闭环”拆分。

分工时遵循以下原则：

1. 每个人尽量负责独立领域，减少多人同时修改同一文件。
2. 数据模型、接口 Schema、路由和服务逻辑按业务模块拆分。
3. `app/main.py`、公共配置、数据库连接等共享文件由一人集中维护，其他成员尽量少改。
4. AI 能力第一阶段可先使用 Mock 数据打通流程，后续再接入真实模型接口。
5. 测试负责人从开发初期同步维护测试用例和接口验收清单，不等到最后集中测试。

## 3. 开发成员 A：基础平台与资料处理

### 3.1 负责方向

开发成员 A 负责账号体系、课程/考试目标、资料上传、资料解析和任务状态等后端基础能力。

该成员主要保障学生能够完成：

资料上传 -> 资料存储 -> 文本提取/OCR -> 解析状态查看

### 3.2 主要功能

- 用户注册、登录、JWT 鉴权。
- 学生和管理员角色区分。
- 当前登录用户信息获取。
- 课程/考试目标创建、查看、更新、删除。
- 考试日期、复习目标等基础信息维护。
- PDF、TXT、图片资料上传。
- 文件类型、文件大小校验。
- 资料列表、资料详情、资料预览、资料删除。
- 资料解析状态维护。
- PDF/TXT 文本提取。
- 图片 OCR 流程预留或 Mock。
- 解析失败任务记录与重试入口。

### 3.3 建议负责文件

```text
app/models/user.py
app/models/study_target.py
app/models/material.py

app/schemas/auth.py
app/schemas/user.py
app/schemas/study_target.py
app/schemas/material.py

app/routers/auth.py
app/routers/users.py
app/routers/study_targets.py
app/routers/materials.py

app/services/auth_service.py
app/services/material_service.py
app/services/parser_service.py

app/core/security.py
```

### 3.4 对外提供的数据能力

开发成员 A 需要向开发成员 B 提供稳定的数据基础：

- 用户 ID。
- 课程/考试目标 ID。
- 资料 ID。
- 资料解析文本。
- 资料解析状态。
- 资料所属用户和所属目标。

AI 学习闭环相关模块应基于这些数据继续处理，不重复实现资料上传和解析逻辑。

## 4. 开发成员 B：AI 学习闭环

### 4.1 负责方向

开发成员 B 负责知识提炼、AI 问答、AI 出题、自测评分、错题本和复习计划等核心学习闭环能力。

该成员主要保障学生能够完成：

AI 知识提炼 -> AI 问答 -> AI 出题自测 -> 错题沉淀 -> 复习计划生成

### 4.2 主要功能

- 根据资料解析文本生成摘要。
- 根据资料解析文本生成章节大纲。
- 生成关键词、重点知识点和可能考点。
- 基于指定资料进行 AI 问答。
- 保存问答记录。
- 根据资料生成单选题、多选题、判断题。
- 支持题目难度、数量、题型参数。
- 支持在线自测提交。
- 自动评分。
- 返回正确答案和答案解析。
- 将答错题目自动写入错题本。
- 错题按课程、知识点、掌握状态筛选。
- 错题掌握状态更新。
- 根据考试日期、错题情况和学习进度生成复习计划。

### 4.3 建议负责文件

```text
app/models/knowledge.py
app/models/question.py
app/models/test_record.py
app/models/wrong_question.py
app/models/review_plan.py

app/schemas/knowledge.py
app/schemas/qa.py
app/schemas/question.py
app/schemas/test_record.py
app/schemas/wrong_question.py
app/schemas/review_plan.py

app/routers/knowledge.py
app/routers/qa.py
app/routers/questions.py
app/routers/tests.py
app/routers/wrong_questions.py
app/routers/review_plans.py

app/services/ai_service.py
app/services/question_service.py
app/services/test_service.py
app/services/wrong_question_service.py
app/services/review_plan_service.py
```

### 4.4 对外依赖的数据能力

开发成员 B 主要依赖开发成员 A 提供：

- 已登录用户信息。
- 课程/考试目标信息。
- 已上传资料信息。
- 资料解析后的文本内容。
- 资料解析完成状态。

在资料解析未完成时，AI 相关接口应返回明确提示，不应自行处理文件解析。

## 5. 测试负责人：接口测试与集成验收

### 5.1 负责方向

测试负责人主要负责测试资产、接口验收、主流程验证和合并前质量检查。

测试负责人不直接承担大规模业务编码，但需要从开发早期开始同步维护测试用例，保证每个阶段都有可验证结果。

### 5.2 主要职责

- 建立 `tests/` 测试目录。
- 编写健康检查测试。
- 编写注册、登录、鉴权测试。
- 编写课程/考试目标接口测试。
- 编写资料上传、列表、解析状态测试。
- 编写知识提炼、问答、出题测试。
- 编写自测提交、评分、错题沉淀测试。
- 编写复习计划生成测试。
- 维护接口测试文档或 Apifox/Postman 集合。
- 维护核心业务闭环验收清单。
- 每次合并前执行主流程检查。

### 5.3 建议负责文件

```text
tests/
tests/conftest.py
tests/test_health.py
tests/test_auth.py
tests/test_study_targets.py
tests/test_materials.py
tests/test_ai_flow.py
tests/test_tests_and_wrong_questions.py
tests/test_review_plans.py

docs/api.md
docs/test-plan.md
```

### 5.4 验收重点

测试负责人重点验证以下流程：

1. 用户注册登录成功。
2. 登录后可以创建课程/考试目标。
3. 可以上传资料并看到解析状态。
4. 资料解析完成后可以生成知识提炼结果。
5. 可以基于资料进行问答。
6. 可以生成自测题。
7. 提交答案后可以得到评分和解析。
8. 错题可以自动进入错题本。
9. 可以根据错题和考试日期生成复习计划。
10. 管理员可以查看用户、资料、AI 调用记录和异常任务。

## 6. 建议先建立的公共骨架

为了减少后续冲突，建议在正式开发前先由一名成员单独提交一次公共骨架。

建议新增目录：

```text
app/models/
app/schemas/
app/services/
app/repositories/
app/utils/
tests/
docs/
```

建议统一的接口响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

建议统一的分页格式：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

## 7. 分支与合并建议

建议三名成员分别使用独立分支：

```text
feature/auth-materials
feature/ai-learning-flow
feature/tests-docs
```

合并建议：

1. 先合并公共骨架分支。
2. 再合并基础平台与资料处理分支。
3. 再合并 AI 学习闭环分支。
4. 最后合并测试与文档分支。

每次合并前至少检查：

```bash
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/redis
```

如果已经建立测试用例，则额外执行：

```bash
pytest
```

## 8. 冲突控制规则

为减少合并冲突，建议团队遵守以下规则：

1. 不把所有模型写入同一个 `models.py` 文件，按领域拆分模型文件。
2. 不把所有 Schema 写入同一个 `schemas.py` 文件，按接口领域拆分。
3. 不把所有业务逻辑写进路由文件，复杂逻辑放入 `services/`。
4. `app/main.py` 由一人负责集中注册路由。
5. 公共配置、数据库连接、统一异常处理等共享代码修改前先在群里同步。
6. AI 接口先统一返回结构，真实模型调用可以后续替换。
7. 每个 Pull Request 尽量只包含一个领域的改动。
8. 合并前先从主分支同步，解决本地冲突后再提交。

## 9. 第一阶段开发优先级

第一阶段优先打通最小可展示闭环：

1. 登录注册。
2. 创建课程/考试目标。
3. 上传资料。
4. 资料解析生成文本，允许先 Mock。
5. 知识提炼，允许先 Mock。
6. AI 出题，允许先 Mock。
7. 提交测试并评分。
8. 错题自动记录。
9. 生成复习计划，允许先使用规则生成。
10. 管理员查看用户、资料、AI 调用记录和异常任务。

完成以上内容后，再补充接口细节、异常处理、测试覆盖和管理员端增强能力。
