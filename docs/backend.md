# 后端综合文档

本文档面向后端开发、接口联调和系统说明，覆盖当前 FastAPI 后端的架构、接口模块、数据流、任务流和外部依赖。

## 1. 技术栈与目录结构

| 类型 | 当前实现 |
| --- | --- |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy async |
| 数据库 | PostgreSQL 16，测试环境可使用 SQLite |
| 迁移 | Alembic |
| 任务队列 | Celery + Redis |
| 文件解析 | pypdf, pdf2image, Tesseract OCR, Pillow |
| AI 调用 | mock provider 或 OpenAI-compatible Chat Completions |
| 认证 | JWT Bearer Token |

主要目录：

```text
app/
  routers/        API 路由
  schemas/        Pydantic 请求和响应模型
  models/         SQLAlchemy 数据模型
  repositories/   数据访问层
  services/       业务服务层
  dependencies/   认证和依赖注入
  core/           配置与安全工具
  db/             数据库连接
alembic/          数据库迁移
tests/            后端自动化测试
```

## 2. 应用入口与路由

应用入口为 `app/main.py`。启动时会执行 `BootstrapService.ensure_initial_admin()`，如果 `.env` 中配置了初始管理员账号且数据库中不存在该用户名，则自动创建管理员。

已注册路由模块：

| 模块 | 前缀 | 说明 |
| --- | --- | --- |
| 健康检查 | `/health` | API、数据库、Redis 健康状态 |
| 认证 | `/auth` | 注册、登录 |
| 用户 | `/users` | 当前用户信息 |
| 学习目标 | `/study-targets` | 目标 CRUD、目标级 chunks |
| 资料 | `/materials` | 上传、列表、详情、解析、源文件、结构化内容 |
| 知识提炼 | `/knowledge` | 最新提炼结果、同步提炼 |
| 知识作业 | `/knowledge-jobs` | 后台提炼和图谱刷新作业 |
| 知识图谱 | `/knowledge-graphs` | 生成/获取目标图谱 |
| 知识点 | `/knowledge-points` | 证据、关联题目、错题、掌握度 |
| QA | `/qa` | AI 问答和历史 |
| 题目 | `/questions` | 出题、提示、解析、追问 |
| 自测 | `/tests` | 提交测试并评分 |
| 错题 | `/wrong-questions` | 错题列表、复做、掌握状态 |
| 复习计划 | `/review-plans` | 生成、列表、任务完成状态 |
| 导出 | `/exports` | Markdown/CSV 导出 |
| AI 用量 | `/ai-usage` | token、费用估算、调用日志 |
| 管理员 | `/admin` | 用户、资料、解析任务、日志和总览 |

## 3. 统一响应和认证

业务接口通常返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页接口的 `data` 为：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

认证方式：

```http
Authorization: Bearer <access_token>
```

未携带 token、token 类型不是 Bearer、token 过期、签名无效、用户被停用，都会被拒绝。管理员接口要求当前用户 `role=admin`。

文件下载和预览接口不使用统一 JSON 包装，成功时直接返回文件流。

## 4. 核心业务闭环

```text
注册/登录
-> 创建学习目标
-> 上传 TXT/PDF/图片资料
-> 后台解析并生成结构化内容
-> 资料级和目标级知识提炼
-> 生成知识图谱和掌握度
-> AI 问答
-> AI 出题
-> 提交自测并评分
-> 生成错题和知识点表现
-> 复做错题
-> 生成复习计划
-> 导出错题、计划、知识总结或 Anki CSV
```

## 5. 主要接口清单

### 5.1 认证与用户

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册学生账号 |
| `POST` | `/auth/login` | 登录并返回 token |
| `GET` | `/users/me` | 当前登录用户 |

注册字段：

| 字段 | 约束 |
| --- | --- |
| `username` | 3 到 50 字符，唯一 |
| `password` | 6 到 72 字符 |
| `display_name` | 可选，最多 50 字符 |

### 5.2 学习目标

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/study-targets` | 创建目标 |
| `GET` | `/study-targets` | 分页列表 |
| `GET` | `/study-targets/{target_id}` | 详情 |
| `GET` | `/study-targets/{target_id}/chunks` | 目标下已解析资料 chunks |
| `PATCH` | `/study-targets/{target_id}` | 更新 |
| `DELETE` | `/study-targets/{target_id}` | 删除 |

`target_type` 可选：

```text
course
exam
```

### 5.3 资料上传、解析和结构化内容

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/materials` | 上传资料，默认自动解析 |
| `GET` | `/materials` | 分页列表，可按 `target_id` 筛选 |
| `GET` | `/materials/{material_id}` | 资料详情 |
| `GET` | `/materials/{material_id}/preview` | 文本预览和解析文本 |
| `GET` | `/materials/{material_id}/file` | 源文件流 |
| `POST` | `/materials/{material_id}/parse` | 创建解析任务 |
| `DELETE` | `/materials/{material_id}` | 软删除资料 |

结构化接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/materials/{id}/sections` | 章节目录 |
| `GET` | `/materials/{id}/chunks` | 文本块，可按 `section_id` 筛选 |
| `GET` | `/materials/{id}/figures` | 图片、几何图、流程图说明 |
| `GET` | `/materials/{id}/tables` | 表格内容 |
| `GET` | `/materials/{id}/formulas` | 公式和解释 |
| `GET` | `/materials/{id}/structured` | 一次性返回上述结构 |

资料状态：

| 状态 | 含义 | AI 是否可用 |
| --- | --- | --- |
| `uploaded` | 已上传，未解析 | 否 |
| `parsing` | 解析任务运行中 | 否 |
| `parsed` | 解析成功 | 是 |
| `failed` | 解析失败 | 否 |

支持的文件：

| 类型 | 处理方式 |
| --- | --- |
| TXT | 读取 UTF-8 文本 |
| 文本型 PDF | 使用 `pypdf` 提取文本 |
| 扫描型 PDF | `pdf2image` 转图片后使用 Tesseract OCR |
| 图片 | 使用 Tesseract OCR，可选视觉模型增强 |

## 6. AI 与知识能力

### 6.1 AI provider

默认：

```env
AI_PROVIDER=mock
```

真实模型：

```env
AI_PROVIDER=openai-compatible
AI_API_KEY=your_key
AI_BASE_URL=https://example.com/v1
AI_MODEL=your-model
AI_TIMEOUT_SECONDS=30
```

真实 AI 配置错误、网络失败、超时或返回格式异常时，接口会返回明确错误，不会静默降级到 mock。

### 6.2 知识提炼

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/knowledge/latest` | 读取最新资料级或目标级提炼结果 |
| `POST` | `/knowledge/extract` | 同步提炼知识点 |

请求范围：

| 字段 | 说明 |
| --- | --- |
| `material_id` | 资料级提炼 |
| `target_id` | 目标级提炼，并可刷新图谱 |
| `material_id + target_id` | 基于某份资料增量刷新目标知识 |
| `force_regenerate` | 是否强制重新生成 |

### 6.3 知识作业

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/knowledge-jobs/material-extract` | 创建资料级提炼作业 |
| `POST` | `/knowledge-jobs/target-extract` | 创建目标级提炼作业 |
| `POST` | `/knowledge-jobs/graph-refresh` | 创建图谱刷新作业 |
| `GET` | `/knowledge-jobs/latest` | 查询最新作业 |
| `GET` | `/knowledge-jobs/{job_id}` | 查询指定作业 |

作业状态：

```text
pending
running
succeeded
failed
```

### 6.4 知识图谱和知识点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/knowledge-graphs/generate` | 生成或刷新知识图谱 |
| `GET` | `/knowledge-graphs/{target_id}` | 获取图谱 |
| `GET` | `/knowledge-points/{id}/materials` | 知识点关联资料证据 |
| `GET` | `/knowledge-points/{id}/questions` | 关联题目 |
| `GET` | `/knowledge-points/{id}/wrong-questions` | 关联错题 |
| `PATCH` | `/knowledge-points/{id}/mastery` | 手动更新掌握度 |

知识点掌握状态：

```text
unlearned
weak
basic
proficient
```

## 7. 练习、错题和复习

### 7.1 AI 问答

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/qa/ask` | 发起问答 |
| `GET` | `/qa/history` | 问答历史 |

问答请求必须至少提供 `material_id` 或 `target_id`。可选 `knowledge_point_id` 或 `knowledge_point_ids` 聚焦知识点。

### 7.2 AI 出题

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/questions/generate` | 生成题目 |
| `GET` | `/questions/{question_id}/hints/{level}` | 获取分级提示 |
| `GET` | `/questions/{question_id}/solution` | 获取完整解析 |
| `POST` | `/questions/{question_id}/explain` | 对某题追问 |

题型：

```text
single_choice
multiple_choice
true_false
subjective
```

难度：

```text
easy
medium
hard
```

### 7.3 自测提交

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/tests/submit` | 提交答案、评分、沉淀错题 |

客观题使用 `answer`，主观题使用 `answer_text`。`answer_file_ids` 和 `answer_file_urls` 为图片/PDF 作答预留，当前不要只传文件答案。

当前后端未暴露 `GET /tests/records`。前端已有调用预留，若需要历史自测列表，需要补充后端路由。

### 7.4 错题本

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/wrong-questions` | 错题列表，支持目标、资料、知识点、掌握状态筛选 |
| `GET` | `/wrong-questions/review-queue` | 加权复习队列 |
| `GET` | `/wrong-questions/{id}` | 错题详情 |
| `POST` | `/wrong-questions/{id}/redo` | 错题复做 |
| `PATCH` | `/wrong-questions/{id}/mastery` | 更新掌握状态 |

### 7.5 复习计划

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/review-plans/generate` | 生成复习计划 |
| `GET` | `/review-plans` | 复习计划列表 |
| `PATCH` | `/review-plans/tasks/{task_id}` | 标记任务完成或未完成 |

计划生成会综合知识点掌握度、错题数量、正确率和资料证据。

## 8. 导出和 AI 用量

导出接口：

| 路径 | 类型 |
| --- | --- |
| `/exports/wrong-questions.md` | Markdown |
| `/exports/review-plan/{plan_id}.md` | Markdown |
| `/exports/knowledge-summary/{target_id}.md` | Markdown |
| `/exports/anki/{target_id}.csv` | CSV |

AI 用量接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/ai-usage/summary` | 汇总 token、调用次数、估算费用 |
| `GET` | `/ai-usage/logs` | 调用明细 |

`estimated_cost` 使用本地配置的单价估算，不代表模型供应商官方账单。

## 9. 管理员能力

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/admin/summary` | 后台总览 |
| `GET` | `/admin/users` | 用户列表 |
| `PATCH` | `/admin/users/{id}/status` | 启用/停用用户 |
| `GET` | `/admin/materials` | 全局资料列表 |
| `GET` | `/admin/tasks` | 解析任务列表 |
| `POST` | `/admin/tasks/{task_id}/retry` | 重试解析任务 |
| `GET` | `/admin/logs` | 管理员操作日志 |

普通学生访问 `/admin/*` 会被拒绝。

## 10. 后端维护注意事项

1. 新接口应保持统一响应格式，文件流接口除外。
2. 涉及用户数据的查询必须校验 `user_id`，防止跨用户访问。
3. AI 能力只应消费 `parse_status=parsed` 的资料。
4. 资料解析任务应记录 `parse_error` 和 `parse_warning`，便于前端展示。
5. 真实 AI provider 不应自动 fallback 到 mock，以免掩盖集成问题。
6. 新增数据表后需要补 Alembic 迁移，并确保 `tests/conftest.py` 导入对应模型。
7. 若补齐 `GET /tests/records`，需同步更新前端类型和测试文档。
