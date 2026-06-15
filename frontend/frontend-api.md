# 前端接口联调文档

本文档面向前端组，说明当前后端各模块关系、接口调用顺序、鉴权方式、请求响应结构和当前实现状态。当前后端基于 FastAPI，启动后可通过 Swagger 查看接口：

```text
http://localhost:8000/docs
```

默认本地接口地址：

```text
http://localhost:8000
```

## 1. 模块关系

当前后端分为基础平台模块和 AI 学习闭环模块。

```text
认证模块 auth/users
  -> 提供用户注册、登录、当前用户信息
  -> 后续所有业务接口通过 JWT 识别当前用户

课程/考试目标模块 study-targets
  -> 用户创建复习目标，例如“软件工程期末复习”
  -> 资料、复习计划等数据都可以挂在某个 target 下

资料模块 materials
  -> 上传 PDF/TXT/图片资料
  -> 保存资料元数据、文件路径、解析状态、解析文本
  -> AI 模块只读取 parse_status == parsed 的资料

AI 学习模块 knowledge / qa / questions
  -> 基于 materials.parsed_text 做知识提炼、问答、出题
  -> QA 已接入真实 materials 表、文本模型调用入口和 qa_records 持久化

测试、错题、复习计划模块 tests / wrong-questions / review-plans
  -> 当前以接口骨架和响应结构为主
  -> 后续会接入 questions、test_records、wrong_questions、review_plans 等持久化逻辑
```

前端推荐的主流程：

```text
注册/登录
-> 获取 token
-> 创建 study target
-> 上传 material
-> 等待或触发资料解析完成
-> 在资料详情页调用知识提炼 / QA / 出题
-> QA 结果写入历史记录
-> 查看 QA 历史
```

## 2. 通用规范

### 2.1 统一响应格式

成功响应统一为：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页响应统一为：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 10
  }
}
```

部分异常由 FastAPI 直接返回：

```json
{
  "detail": "未提供认证令牌"
}
```

或：

```json
{
  "detail": "Material not found."
}
```

### 2.2 鉴权方式

除健康检查、注册、登录外，业务接口都需要 Bearer Token。

请求头：

```text
Authorization: Bearer <access_token>
```

前端登录成功后，应保存：

```text
data.token.access_token
```

后续请求统一放入 `Authorization` 请求头。

### 2.3 枚举值

用户角色：

```text
student
admin
```

课程/考试目标类型：

```text
course
exam
```

资料类型：

```text
pdf
txt
image
```

资料解析状态：

```text
uploaded
parsing
parsed
failed
```

题型：

```text
single_choice
multiple_choice
true_false
```

题目难度：

```text
easy
medium
hard
```

错题掌握状态：

```text
unmastered
reviewing
mastered
```

## 3. 接口状态总览

| 模块 | 接口 | 状态 | 前端建议 |
|---|---|---|---|
| 健康检查 | `/health` | 可用 | 开发环境检查 |
| 认证 | `/auth/register`, `/auth/login` | 可用 | 优先联调 |
| 当前用户 | `/users/me` | 可用 | 页面初始化获取用户信息 |
| 课程/考试目标 | `/study-targets` | 可用 | 可用于目标管理页面 |
| 资料 | `/materials` | 可用 | 可用于资料上传、列表、详情、预览 |
| 知识提炼 | `/knowledge/extract` | 可运行，当前以结构化 Mock 为主 | 可先联调展示结构 |
| QA 问答 | `/qa/ask` | 可用，已读真实 materials 并保存记录 | 优先联调 |
| QA 历史 | `/qa/history` | 可用 | 可用于问答历史面板 |
| AI 出题 | `/questions/generate` | 可运行，当前以结构化 Mock 为主 | 可先联调题目展示 |
| 自测提交 | `/tests/submit` | 骨架阶段 | 暂不作为核心联调 |
| 错题本 | `/wrong-questions` | 骨架阶段 | 暂不作为核心联调 |
| 复习计划 | `/review-plans` | 骨架阶段 | 暂不作为核心联调 |

## 4. 健康检查

### 4.1 API 健康检查

```text
GET /health
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "ok"
  }
}
```

### 4.2 数据库健康检查

```text
GET /health/db
```

### 4.3 Redis 健康检查

```text
GET /health/redis
```

## 5. 认证与用户

### 5.1 注册

```text
POST /auth/register
```

请求体：

```json
{
  "username": "student1",
  "password": "123456",
  "display_name": "学生1"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": 1,
      "username": "student1",
      "display_name": "学生1",
      "role": "student",
      "is_active": true,
      "created_at": "2026-05-27T10:00:00Z"
    }
  }
}
```

### 5.2 登录

```text
POST /auth/login
```

请求体：

```json
{
  "username": "student1",
  "password": "123456"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": {
      "access_token": "JWT_TOKEN",
      "token_type": "bearer"
    },
    "user": {
      "id": 1,
      "username": "student1",
      "display_name": "学生1",
      "role": "student",
      "is_active": true,
      "created_at": "2026-05-27T10:00:00Z"
    }
  }
}
```

### 5.3 当前用户

```text
GET /users/me
Authorization: Bearer <token>
```

响应结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": 1,
      "username": "student1",
      "display_name": "学生1",
      "role": "student",
      "is_active": true,
      "created_at": "2026-05-27T10:00:00Z"
    }
  }
}
```

## 6. 课程/考试目标

### 6.1 创建目标

```text
POST /study-targets
Authorization: Bearer <token>
```

请求体：

```json
{
  "title": "软件工程期末复习",
  "subject": "软件工程",
  "target_type": "exam",
  "exam_date": "2026-06-20",
  "review_goal": "掌握需求分析、系统设计、测试和维护",
  "description": "期末复习目标"
}
```

响应结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "target": {
      "id": 1,
      "user_id": 1,
      "title": "软件工程期末复习",
      "subject": "软件工程",
      "target_type": "exam",
      "exam_date": "2026-06-20",
      "review_goal": "掌握需求分析、系统设计、测试和维护",
      "description": "期末复习目标",
      "created_at": "2026-05-27T10:00:00Z",
      "updated_at": "2026-05-27T10:00:00Z"
    }
  }
}
```

### 6.2 目标列表

```text
GET /study-targets?page=1&page_size=10
Authorization: Bearer <token>
```

返回分页结构，`items` 中每项为 `StudyTargetResponse`。

### 6.3 目标详情

```text
GET /study-targets/{target_id}
Authorization: Bearer <token>
```

### 6.4 修改目标

```text
PATCH /study-targets/{target_id}
Authorization: Bearer <token>
```

请求体所有字段均可选：

```json
{
  "title": "软件工程冲刺复习",
  "review_goal": "重点复习需求分析和软件测试"
}
```

### 6.5 删除目标

```text
DELETE /study-targets/{target_id}
Authorization: Bearer <token>
```

当前为软删除。

## 7. 资料模块

### 7.1 上传资料

```text
POST /materials
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| target_id | int | 所属课程/考试目标 ID |
| file | file | 上传文件，支持 PDF、TXT、图片 |

curl 示例：

```bash
curl -X POST http://localhost:8000/materials \
  -H "Authorization: Bearer $TOKEN" \
  -F "target_id=1" \
  -F "file=@/tmp/se_review.txt;type=text/plain"
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material": {
      "id": 1,
      "user_id": 1,
      "target_id": 1,
      "original_filename": "se_review.txt",
      "stored_filename": "uuid.txt",
      "file_type": "txt",
      "content_type": "text/plain",
      "file_size": 128,
      "parse_status": "uploaded",
      "parse_error": null,
      "created_at": "2026-05-27T10:00:00Z",
      "updated_at": "2026-05-27T10:00:00Z"
    }
  }
}
```

说明：

- `MaterialResponse` 不直接返回完整 `parsed_text`。
- AI 接口会在后端读取 `parsed_text`。
- 当前如果 parse 逻辑尚未自动完成，前端应根据 `parse_status` 判断是否允许触发 AI 功能。

### 7.2 资料列表

```text
GET /materials?page=1&page_size=10&target_id=1
Authorization: Bearer <token>
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| target_id | int | 否 | 按课程/考试目标筛选 |

### 7.3 资料详情

```text
GET /materials/{material_id}
Authorization: Bearer <token>
```

### 7.4 资料预览

```text
GET /materials/{material_id}/preview
Authorization: Bearer <token>
```

响应结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material": {},
    "preview_text": "TXT 资料预览文本",
    "message": "success"
  }
}
```

说明：

- 当前阶段 TXT 可返回文本预览。
- PDF 和图片可能返回提示信息。

### 7.5 删除资料

```text
DELETE /materials/{material_id}
Authorization: Bearer <token>
```

当前为软删除。

## 8. AI 知识提炼

```text
POST /knowledge/extract
Authorization: Bearer <token>
```

请求体：

```json
{
  "material_id": 1,
  "target_id": 1
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material_id": 1,
    "summary": "本资料主要内容包括……",
    "outline": ["资料核心内容梳理", "重要概念与定义", "复习重点与可能考点"],
    "keywords": ["需求分析", "系统设计"],
    "key_points": ["理解需求分析相关概念和使用场景。"],
    "exam_points": ["关注需求分析在题目中的定义、判断或应用。"]
  }
}
```

当前状态：

- 可用于前端展示结构联调。
- 当前主要是结构化 Mock/规则生成。
- 后续会接入真实文本模型和结果持久化。

## 9. AI 问答

### 9.1 提问

```text
POST /qa/ask
Authorization: Bearer <token>
```

请求体：

```json
{
  "material_id": 1,
  "question": "需求分析和系统设计有什么区别？"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "qa_record_id": 1,
    "question": "需求分析和系统设计有什么区别？",
    "answer": "需求分析关注系统要做什么，系统设计关注如何实现。",
    "references": [
      {
        "material_id": 1,
        "snippet": "需求分析用于明确系统边界、用户角色、功能范围和验收标准。"
      }
    ],
    "created_at": "2026-05-27T10:00:00+00:00"
  }
}
```

当前状态：

- 已接入真实 `materials` 表。
- 仅当 `parse_status == parsed` 时可用。
- 已有 OpenAI-compatible 文本模型调用入口。
- 当前已用 DeepSeek API 对 QA 链路做过初步验证。
- 回答会保存到 `qa_records`。

常见错误：

```json
{
  "detail": "Material not found."
}
```

```json
{
  "detail": "Material is not parsed yet."
}
```

### 9.2 QA 历史

```text
GET /qa/history?page=1&page_size=10
Authorization: Bearer <token>
```

按资料筛选：

```text
GET /qa/history?material_id=1&page=1&page_size=10
Authorization: Bearer <token>
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "qa_record_id": 1,
        "material_id": 1,
        "question": "需求分析的主要目标是什么？",
        "answer": "需求分析的主要目标是明确系统边界、用户角色、功能范围和验收标准。",
        "references": [],
        "ai_provider": "openai-compatible",
        "ai_model": "deepseek-v4-flash",
        "created_at": "2026-05-27T10:00:00+00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

说明：

- 只返回当前登录用户自己的历史记录。
- 可用于资料详情页右侧问答历史、独立 AI 问答页历史列表等场景。

## 10. AI 出题

```text
POST /questions/generate
Authorization: Bearer <token>
```

请求体：

```json
{
  "material_id": 1,
  "question_types": ["single_choice", "multiple_choice", "true_false"],
  "difficulty": "medium",
  "count": 5
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material_id": 1,
    "questions": [
      {
        "id": 1001,
        "type": "single_choice",
        "stem": "关于「需求分析」，下列说法最符合资料内容的是哪一项？",
        "options": [
          {"key": "A", "text": "需求分析是资料中的重要复习点。"},
          {"key": "B", "text": "需求分析与本资料完全无关。"}
        ],
        "correct_answer": ["A"],
        "analysis": "资料中围绕需求分析展开了说明，因此 A 项正确。",
        "knowledge_points": ["需求分析"],
        "difficulty": "medium"
      }
    ]
  }
}
```

当前状态：

- 可用于前端题目展示和答题 UI 联调。
- 当前题目生成主要是结构化 Mock/规则生成。
- 题目暂未持久化，后续会接入 `questions` 表。

## 11. 自测、错题与复习计划

以下接口当前更偏向接口骨架和前端结构预留。前端可以先按响应结构设计页面，但不建议作为当前核心联调目标。

### 11.1 提交自测

```text
POST /tests/submit
Authorization: Bearer <token>
```

请求体：

```json
{
  "material_id": 1,
  "target_id": 1,
  "answers": [
    {
      "question_id": 1001,
      "answer": ["A"]
    }
  ]
}
```

规划响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "test_record_id": 1,
    "score": 100,
    "accuracy": 1,
    "total_count": 1,
    "correct_count": 1,
    "wrong_count": 0,
    "results": [
      {
        "question_id": 1001,
        "user_answer": ["A"],
        "correct_answer": ["A"],
        "is_correct": true,
        "analysis": "资料中围绕需求分析展开了说明，因此 A 项正确。"
      }
    ]
  }
}
```

### 11.2 错题列表

```text
GET /wrong-questions?page=1&page_size=10
Authorization: Bearer <token>
```

### 11.3 错题详情

```text
GET /wrong-questions/{wrong_question_id}
Authorization: Bearer <token>
```

### 11.4 更新错题掌握状态

```text
PATCH /wrong-questions/{wrong_question_id}/mastery
Authorization: Bearer <token>
```

请求体：

```json
{
  "mastery_status": "reviewing"
}
```

### 11.5 生成复习计划

```text
POST /review-plans/generate
Authorization: Bearer <token>
```

请求体：

```json
{
  "target_id": 1,
  "start_date": "2026-05-27",
  "end_date": "2026-06-20"
}
```

### 11.6 复习计划列表

```text
GET /review-plans?page=1&page_size=10
Authorization: Bearer <token>
```

## 12. 推荐前端页面与接口对应关系

| 前端页面 | 后端接口 |
|---|---|
| 登录页 | `POST /auth/login` |
| 注册页 | `POST /auth/register` |
| 页面初始化 / 用户菜单 | `GET /users/me` |
| 目标管理页 | `GET /study-targets`, `POST /study-targets`, `PATCH /study-targets/{id}`, `DELETE /study-targets/{id}` |
| 资料库页 | `GET /materials`, `POST /materials`, `DELETE /materials/{id}` |
| 资料详情页 | `GET /materials/{id}`, `GET /materials/{id}/preview` |
| 知识提炼面板 | `POST /knowledge/extract` |
| AI 问答面板 | `POST /qa/ask`, `GET /qa/history?material_id={id}` |
| 出题练习面板 | `POST /questions/generate` |
| 自测结果页 | `POST /tests/submit` |
| 错题本页 | `GET /wrong-questions`, `PATCH /wrong-questions/{id}/mastery` |
| 复习计划页 | `POST /review-plans/generate`, `GET /review-plans` |

## 13. 当前最稳定联调路径

建议前端优先联调以下闭环：

```text
1. POST /auth/register
2. POST /auth/login
3. GET /users/me
4. POST /study-targets
5. POST /materials
6. GET /materials
7. GET /materials/{id}
8. POST /qa/ask
9. GET /qa/history
```

注意：

- `/qa/ask` 要求资料 `parse_status == parsed`。
- 如果解析流程尚未自动触发，后端测试时可能会手动写入 `parsed_text`。
- 前端页面上建议根据 `parse_status` 控制 AI 按钮状态：
  - `uploaded`：显示“等待解析”
  - `parsing`：显示“解析中”
  - `parsed`：允许知识提炼、问答、出题
  - `failed`：显示失败原因和重试入口

## 14. 前端需要注意的字段

### 14.1 MaterialResponse 不含 parsed_text

资料列表和详情不会直接返回完整解析文本，避免大文本影响列表性能。AI 功能由后端内部读取 `materials.parsed_text`。

### 14.2 QA references 可为空

`references` 是数组。真实模型回答时，后端会尽量返回资料片段，但某些情况下可能为空。前端展示时应兼容：

```json
"references": []
```

### 14.3 当前 AI 出题 ID 可能不是数据库 ID

`/questions/generate` 当前仍以结构化 Mock 为主，返回的 `id` 主要用于前端临时展示和答题 UI。后续题目持久化后，该字段会切换为真实数据库题目 ID。

### 14.4 日期字段

当前日期字段主要使用 ISO 字符串，例如：

```text
2026-05-27
2026-05-27T10:00:00Z
```

前端建议统一按 ISO 格式处理。
