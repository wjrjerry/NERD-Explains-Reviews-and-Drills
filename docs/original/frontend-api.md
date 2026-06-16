# NERD 后端前端接口文档

本文档面向前端联调，描述当前后端可用接口、认证方式、关键数据流程和页面对接建议。

## 1. 基础约定

### 1.1 服务地址

本地默认地址：

```text
http://localhost:8000
```

Swagger 文档：

```text
http://localhost:8000/docs
```

### 1.2 统一 JSON 响应

大多数业务接口返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页接口的 `data`：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

导出接口例外，直接返回 Markdown 或 CSV 文件内容。

### 1.3 认证

登录成功后，前端保存 `access_token`，后续请求统一携带：

```http
Authorization: Bearer <access_token>
```

未携带或 token 失效时会返回 401。

## 2. 当前模块关系

```text
用户 auth/users
  -> 学习目标 study-targets
    -> 资料 materials
      -> 后台解析 parse_tasks
      -> parsed_text
      -> 自动资料级知识提炼
      -> 自动目标级知识提炼
      -> 自动目标级知识图谱刷新
    -> 知识图谱 knowledge-graphs / knowledge-points
    -> QA qa
    -> 题目 questions
    -> 自测 tests
    -> 错题 wrong-questions
    -> 复习计划 review-plans
    -> 导出 exports
    -> AI 用量 ai-usage
```

前端主线推荐以 `target_id` 作为学习空间核心：一个目标下有多份资料、多个知识点、多个题目、错题和复习计划。

## 3. 认证与用户

### 注册

```http
POST /auth/register
Content-Type: application/json
```

```json
{
  "username": "student1",
  "password": "123456",
  "display_name": "学生1"
}
```

### 登录

```http
POST /auth/login
Content-Type: application/json
```

```json
{
  "username": "student1",
  "password": "123456"
}
```

响应中的 token：

```json
{
  "token": {
    "access_token": "...",
    "token_type": "bearer"
  },
  "user": {
    "id": 1,
    "username": "student1",
    "display_name": "学生1",
    "role": "student",
    "is_active": true
  }
}
```

### 当前用户

```http
GET /users/me
Authorization: Bearer <token>
```

## 4. 学习目标

### 创建目标

```http
POST /study-targets
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "title": "软件工程期末复习",
  "subject": "软件工程",
  "target_type": "exam",
  "exam_date": "2026-06-30",
  "review_goal": "掌握需求分析、系统设计和软件测试",
  "description": "课程期末备考"
}
```

`target_type` 可选：

```text
course
exam
```

### 目标列表

```http
GET /study-targets?page=1&page_size=10
```

### 目标详情

```http
GET /study-targets/{target_id}
```

### 目标下结构化文本块

```http
GET /study-targets/{target_id}/chunks?limit=200
```

返回当前目标下所有已解析资料的结构化文本块，适合做目标级资料浏览、检索预览或调试 AI 上下文。

### 更新目标

```http
PATCH /study-targets/{target_id}
```

### 删除目标

```http
DELETE /study-targets/{target_id}
```

## 5. 资料上传、解析与预览

### 5.1 上传资料

```http
POST /materials
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `target_id` | int | 所属目标 ID |
| `auto_parse` | bool | 是否上传后自动解析，默认 `true` |
| `file` | file | PDF、TXT、PNG、JPG、JPEG、WEBP |

示例：

```bash
curl -X POST http://localhost:8000/materials \
  -H "Authorization: Bearer $TOKEN" \
  -F "target_id=1" \
  -F "auto_parse=true" \
  -F "file=@/tmp/se_review.txt;type=text/plain"
```

重要变化：

- 默认 `auto_parse=true`。
- 上传成功后资料通常立即进入 `parsing`。
- 后端会在后台执行解析任务，前端需要轮询资料详情或列表。
- 如果传 `auto_parse=false`，资料初始为 `uploaded`，前端可之后手动调用解析接口。

### 5.2 资料状态

`parse_status` 可选：

```text
uploaded   已上传，尚未解析
parsing    正在后台解析
parsed     解析成功，AI 功能可用
failed     解析失败，查看 parse_error
```

前端按钮建议：

| 状态 | 页面行为 |
|---|---|
| `uploaded` | 显示“待解析”，允许手动解析 |
| `parsing` | 显示“解析中”，禁用 AI 操作并轮询 |
| `parsed` | 允许问答、出题、知识图谱、知识提炼 |
| `failed` | 显示失败原因，允许重新解析 |

资料响应中的核心字段：

```json
{
  "id": 1,
  "target_id": 1,
  "original_filename": "chapter1.pdf",
  "file_type": "pdf",
  "file_size": 102400,
  "parse_status": "parsed",
  "parse_error": null,
  "parse_warning": "PDF 第 3 页 OCR 识别文本较短，可能需要人工校对或视觉解析",
  "created_at": "2026-06-15T10:00:00Z",
  "updated_at": "2026-06-15T10:00:05Z"
}
```

字段说明：

- `parse_error`：解析失败原因，仅在 `parse_status=failed` 时重点展示。
- `parse_warning`：解析质量提示。资料可能已经 `parsed`，但 OCR 质量较低、内容被截断或部分页失败，前端建议用 warning 样式提醒用户。
- `parsed_text`：列表和详情接口不返回完整解析文本。
- `parse_metadata`：后端内部字段，记录 OCR 页数、耗时、失败页码、字符数等过程信息，普通前端接口不返回。

### 5.3 资料列表

```http
GET /materials?page=1&page_size=10&target_id=1
```

### 5.4 资料详情

```http
GET /materials/{material_id}
```

注意：资料详情不返回完整 `parsed_text`，避免大文本拖慢页面。AI 功能由后端内部读取解析文本。

### 5.5 资料预览

```http
GET /materials/{material_id}/preview
```

当前预览接口主要返回 TXT 文本预览。PDF/图片已支持后台解析/OCR，但预览接口仍可能返回提示信息。

### 5.6 源文件预览

```http
GET /materials/{material_id}/file
```

该接口返回用户上传的源文件流，支持 PDF、TXT 和图片。接口需要登录认证，会校验资料归属。

前端注意：

- 该接口不是统一 `{code, message, data}` JSON 响应，成功时直接返回文件。
- 因为浏览器的 `iframe/img` 不能直接附带 `Authorization` 头，前端应先用 `fetch` 携带 token 获取 `Blob`，再用 `URL.createObjectURL(blob)` 生成本地预览地址。
- PDF 可用 `iframe` 预览，图片可用 `img` 预览，TXT/其他文本也可用 `iframe` 或继续使用 `/preview` 的 `preview_text`。
- 切换资料或离开页面时应调用 `URL.revokeObjectURL(url)` 释放本地预览地址。

### 5.7 资料结构化内容

解析成功后，后端会从 `parsed_text` 进一步生成章节和文本块。

章节结构：

```http
GET /materials/{material_id}/sections
```

文本块：

```http
GET /materials/{material_id}/chunks
GET /materials/{material_id}/chunks?section_id=1
```

章节 + 文本块一次性返回：

```http
GET /materials/{material_id}/structured
```

`chunk_type` 可选：

```text
text
definition
formula
example
key_sentence
```

前端可以把它用于资料结构浏览、章节目录、重点句展示；普通 AI 问答/出题流程不需要前端手动提交 chunks。

### 5.7 手动解析或重新解析

```http
POST /materials/{material_id}/parse
```

该接口现在也是后台任务模式：

1. 创建解析任务。
2. 资料状态变为 `parsing`。
3. 立即返回。
4. 前端轮询 `GET /materials/{id}` 查看最终 `parsed` 或 `failed`。

### 5.8 删除资料

```http
DELETE /materials/{material_id}
```

### 5.8 结构化解析结果

解析成功后，后端会在保留 `parsed_text` 的同时生成 MVP 版结构化结果：

```text
material_sections  章节/小节目录
material_chunks    可供知识提炼、问答、出题和知识图谱消费的文本块
material_figures   图片、几何图、流程图说明
material_tables    表格内容
material_formulas  公式与解释
```

#### 查询资料章节

```http
GET /materials/{material_id}/sections
```

响应：

```json
{
  "material_id": 1,
  "sections": [
    {
      "id": 10,
      "material_id": 1,
      "parent_id": null,
      "title": "第一章 需求分析",
      "level": 1,
      "order_index": 1,
      "source_page": null,
      "created_at": "2026-06-15T10:00:00Z",
      "updated_at": "2026-06-15T10:00:00Z"
    }
  ]
}
```

#### 查询资料文本块

```http
GET /materials/{material_id}/chunks
GET /materials/{material_id}/chunks?section_id=10
```

响应：

```json
{
  "material_id": 1,
  "chunks": [
    {
      "id": 100,
      "material_id": 1,
      "section_id": 10,
      "chunk_type": "definition",
      "title": "第一章 需求分析",
      "text": "需求分析是明确系统边界、用户角色和功能范围的过程。",
      "order_index": 1,
      "source_page": null,
      "created_at": "2026-06-15T10:00:00Z",
      "updated_at": "2026-06-15T10:00:00Z"
    }
  ]
}
```

`chunk_type` 可选：

```text
text
definition
formula
example
key_sentence
```

#### 一次性查询结构化结果

#### 查询图片说明

```http
GET /materials/{material_id}/figures
```

响应：

```json
{
  "material_id": 1,
  "figures": [
    {
      "id": 1,
      "material_id": 1,
      "section_id": null,
      "title": "图片说明",
      "description": "图中包含三角形 ABC，点 D 在 BC 上，AD 垂直 BC。",
      "order_index": 1,
      "source_page": null,
      "created_at": "2026-06-15T10:00:00Z",
      "updated_at": "2026-06-15T10:00:00Z"
    }
  ]
}
```

#### 查询表格

```http
GET /materials/{material_id}/tables
```

#### 查询公式

```http
GET /materials/{material_id}/formulas
```

```http
GET /materials/{material_id}/structured
```

响应包含：

```json
{
  "material_id": 1,
  "sections": [],
  "chunks": [],
  "figures": [],
  "tables": [],
  "formulas": []
}
```

#### 查询目标级 chunks

```http
GET /study-targets/{target_id}/chunks?limit=200
```

说明：

- 只返回当前用户该目标下 `parse_status=parsed` 的资料 chunks。
- 主要供目标级知识提炼、目标级 QA、目标级出题和知识图谱使用。
- 前端通常不需要展示全部 chunks，但可用于调试、资料结构页或目标级学习页。

## 6. 自动解析与自动知识提炼流程

上传资料且 `auto_parse=true` 后：

```text
POST /materials
  -> materials.parse_status = parsing
  -> 创建 parse_tasks
  -> BackgroundTasks 执行解析
  -> TXT / PDF 文本 / PDF OCR / 图片 OCR
  -> 成功：materials.parse_status = parsed, 写入 parsed_text / parse_warning / parse_metadata
  -> 生成 material_sections / material_chunks / material_figures / material_tables / material_formulas
  -> 失败：materials.parse_status = failed, 写入 parse_error，必要时写入 parse_warning / parse_metadata
```

OCR 相关说明：

- OCR 语言、超时时间、图片缩放、二值化阈值、PDF OCR DPI、最大页数和 `parsed_text` 最大保存长度均由后端配置控制。
- 图片 OCR 会进行方向纠正、灰度化、放大、自动对比度和二值化。
- 扫描版 PDF 会记录逐页 OCR 状态；普通前端只需要展示 `parse_warning`，不直接读取过程元数据。
- 当 OCR 质量较低时，资料仍可能是 `parsed`，但会返回 `parse_warning`。
- 当解析文本超过后端上限时，后端会截断保存并返回 `parse_warning`，避免 AI 输入过长。

解析成功后后端自动执行：

```text
资料级知识提炼
  -> knowledge_extractions(scope=material)

目标级知识提炼
  -> 汇总当前目标下所有 parsed 资料
  -> knowledge_extractions(scope=target)

目标级知识图谱刷新
  -> knowledge_points
  -> material_knowledge_points
  -> user_knowledge_mastery 初始化或刷新
```

前端通常不需要在每次上传后手动调用知识提炼；只需要轮询资料状态，然后刷新知识提炼/知识图谱页面即可。

## 7. 知识提炼

知识提炼接口仍保留，主要用于手动刷新或失败后重试。

### 资料级知识提炼

```http
POST /knowledge/extract
```

```json
{
  "material_id": 1,
  "force_regenerate": false
}
```

### 目标级知识提炼

```http
POST /knowledge/extract
```

```json
{
  "target_id": 1,
  "force_regenerate": true
}
```

目标级知识提炼会同时刷新目标级知识图谱。

响应核心字段：

```json
{
  "extraction_id": 1,
  "scope": "target",
  "material_id": null,
  "target_id": 1,
  "summary": "...",
  "outline": [],
  "keywords": [],
  "key_points": [],
  "exam_points": [],
  "knowledge_graph": {
    "target_id": 1,
    "nodes": []
  }
}
```

## 8. 知识图谱

### 生成或刷新知识图谱

```http
POST /knowledge-graphs/generate
```

```json
{
  "target_id": 1,
  "force_regenerate": true,
  "max_points": 20
}
```

### 获取知识图谱

```http
GET /knowledge-graphs/{target_id}
```

节点字段：

| 字段 | 说明 |
|---|---|
| `id` | 知识点 ID |
| `parent_id` | 父知识点 ID |
| `name` | 知识点名称 |
| `description` | 描述 |
| `importance_weight` | 重要度，前端可映射圆大小 |
| `level` | 层级 |
| `mastery_status` | 掌握状态 |
| `mastery_score` | 掌握分 |
| `accuracy` | 正确率 |
| `answered_count` | 答题数 |
| `wrong_count` | 错题数 |
| `materials` | 资料证据片段 |

`mastery_status` 可选：

```text
unlearned
weak
basic
proficient
```

前端图谱建议：

- `importance_weight` 映射节点大小。
- `accuracy` / `wrong_count` / `mastery_status` 映射颜色。
- 点击节点后调用知识点详情接口。

## 9. 知识点详情入口

### 知识点关联资料

```http
GET /knowledge-points/{knowledge_point_id}/materials
```

### 知识点关联题目

```http
GET /knowledge-points/{knowledge_point_id}/questions?page=1&page_size=10
```

### 知识点关联错题

```http
GET /knowledge-points/{knowledge_point_id}/wrong-questions?page=1&page_size=10
```

### 手动调整知识点掌握度

```http
PATCH /knowledge-points/{knowledge_point_id}/mastery
```

```json
{
  "mastery_status": "basic",
  "mastery_score": 0.65,
  "next_review_at": "2026-06-20T10:00:00Z"
}
```

## 10. QA 问答

### 提问

```http
POST /qa/ask
```

支持三种范围：

1. 按资料问：

```json
{
  "material_id": 1,
  "question": "需求分析的主要目标是什么？"
}
```

2. 按目标问：

```json
{
  "target_id": 1,
  "question": "需求分析和系统设计有什么区别？"
}
```

3. 按知识点聚焦问：

```json
{
  "target_id": 1,
  "knowledge_point_id": 3,
  "question": "这个知识点最容易考什么？"
}
```

响应会返回 `references` 和 `knowledge_points`。

### QA 历史

```http
GET /qa/history?target_id=1&page=1&page_size=10
GET /qa/history?material_id=1&page=1&page_size=10
```

## 11. AI 出题

### 生成题目

```http
POST /questions/generate
```

按目标和知识点生成：

```json
{
  "target_id": 1,
  "knowledge_point_ids": [3, 4],
  "question_types": ["single_choice", "multiple_choice", "true_false", "subjective"],
  "difficulty": "medium",
  "count": 5,
  "extra_requirement": "偏期末考试风格，选项要有迷惑性"
}
```

按资料生成：

```json
{
  "material_id": 1,
  "question_types": ["single_choice", "subjective"],
  "difficulty": "medium",
  "count": 3
}
```

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

返回的 `questions[].id` 是数据库题目 ID，用于自测提交。

## 12. 自测提交

```http
POST /tests/submit
```

```json
{
  "material_id": 1,
  "target_id": 1,
  "answers": [
    {
      "question_id": 1,
      "answer": ["A"]
    },
    {
      "question_id": 2,
      "answer": ["A", "B"]
    },
    {
      "question_id": 3,
      "answer_text": "需求分析关注做什么，系统设计关注如何做。"
    }
  ]
}
```

说明：

- 客观题用 `answer`。
- 主观题用 `answer_text`。
- `answer_file_ids` / `answer_file_urls` 已预留给后续图片/PDF 作答 OCR，目前不要只传文件答案。
- 提交后会自动评分、生成错题、更新知识点掌握度。

## 13. 错题本

### 错题列表

```http
GET /wrong-questions?target_id=1&material_id=1&knowledge_point_id=3&mastery_status=unmastered&page=1&page_size=10
```

筛选参数均可选。

`mastery_status` 可选：

```text
unmastered
reviewing
mastered
```

### 错题详情

```http
GET /wrong-questions/{wrong_question_id}
```

### 更新错题掌握状态

```http
PATCH /wrong-questions/{wrong_question_id}/mastery
```

```json
{
  "mastery_status": "reviewing"
}
```

## 14. 复习计划

### 生成复习计划

```http
POST /review-plans/generate
```

```json
{
  "target_id": 1,
  "start_date": "2026-06-15",
  "end_date": "2026-06-21"
}
```

如果日期为空，后端会根据当前日期和目标考试日期生成。

复习计划会优先考虑：

- 知识点掌握度。
- 错题数量。
- 低正确率知识点。
- 资料证据。

### 复习计划列表

```http
GET /review-plans?target_id=1&page=1&page_size=10
```

## 15. AI 用量

### 用量汇总

```http
GET /ai-usage/summary?target_id=1&material_id=1
```

返回当前用户真实 AI 调用 token 消耗和本地估算费用。

### 调用明细

```http
GET /ai-usage/logs?page=1&page_size=10&feature=qa&status=success
```

`estimated_cost` 使用本地配置的 token 单价计算，不代表供应商官方账单。

## 16. 导出

导出接口返回文件内容，不使用统一 JSON 包装。

```http
GET /exports/wrong-questions.md?target_id=1
GET /exports/review-plan/{plan_id}.md
GET /exports/knowledge-summary/{target_id}.md
GET /exports/anki/{target_id}.csv
```

返回类型：

- Markdown：`text/markdown; charset=utf-8`
- CSV：`text/csv; charset=utf-8`

## 17. 管理员接口

管理员接口需要登录用户 `role=admin`。

### 用户列表

```http
GET /admin/users?page=1&page_size=10&role=student&is_active=true
```

### 全部资料列表

```http
GET /admin/materials?page=1&page_size=10&user_id=1&target_id=1&parse_status=failed
```

### 解析任务列表

```http
GET /admin/tasks?page=1&page_size=10&status=failed&user_id=1&material_id=1
```

任务状态：

```text
pending
running
succeeded
failed
```

### 重试解析任务

```http
POST /admin/tasks/{task_id}/retry
```

### 管理员操作日志

```http
GET /admin/logs?page=1&page_size=10&operation_type=retry_parse
```

## 18. 推荐前端页面对接

| 页面 | 主要接口 |
|---|---|
| 登录/注册 | `POST /auth/login`, `POST /auth/register` |
| 用户信息 | `GET /users/me` |
| 目标管理 | `/study-targets` |
| 资料库 | `/materials` |
| 资料详情 | `GET /materials/{id}`, `GET /materials/{id}/preview`, `GET /materials/{id}/structured` |
| 解析状态 | `GET /materials/{id}` 轮询 |
| 资料章节/文本块 | `GET /materials/{id}/sections`, `GET /materials/{id}/chunks` |
| 知识提炼 | `POST /knowledge/extract`, `GET /exports/knowledge-summary/{target_id}.md` |
| 知识图谱 | `GET /knowledge-graphs/{target_id}`, `POST /knowledge-graphs/generate` |
| 目标级结构化上下文 | `GET /study-targets/{id}/chunks` |
| 知识点详情 | `/knowledge-points/{id}/materials`, `/questions`, `/wrong-questions` |
| AI 问答 | `POST /qa/ask`, `GET /qa/history` |
| 练习出题 | `POST /questions/generate` |
| 自测 | `POST /tests/submit` |
| 错题本 | `/wrong-questions` |
| 复习计划 | `/review-plans` |
| AI 用量 | `/ai-usage/summary`, `/ai-usage/logs` |
| 导出 | `/exports/*` |
| 管理员 | `/admin/*` |

## 19. 推荐联调流程

```text
1. 注册/登录，保存 token
2. 创建学习目标 POST /study-targets
3. 上传资料 POST /materials，默认 auto_parse=true
4. 轮询 GET /materials/{id}，等待 parse_status=parsed
5. 如需资料目录，获取 GET /materials/{id}/sections 或 /structured
6. 如需目标级上下文，获取 GET /study-targets/{target_id}/chunks
7. 获取 GET /knowledge-graphs/{target_id}
8. 如无图谱或需刷新，调用 POST /knowledge/extract 或 POST /knowledge-graphs/generate
9. 使用 target_id / knowledge_point_id 进行 QA
10. 使用 target_id / knowledge_point_ids 生成题目
11. 提交测试 POST /tests/submit
12. 查看错题、知识点掌握度和复习计划
13. 查看 AI 用量
14. 导出错题本、复习计划、知识提炼或 Anki CSV
```