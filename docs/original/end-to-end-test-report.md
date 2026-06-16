# 后端端到端测试与联调说明

本文档记录当前后端在 Docker 环境下完成的端到端测试结果，供后端协作、Review 和前端联调参考。

测试时间：2026-06-12  
测试环境：Docker Compose，本地 API `http://localhost:8000`  
AI 配置：`AI_PROVIDER=openai-compatible`，模型为 `deepseek-v4-flash`

## 1. 当前完整闭环

```text
用户注册/登录
-> 创建课程/考试目标
-> 上传 TXT 资料
-> POST /materials/{id}/parse 解析 TXT
-> 基于 parsed_text 做知识提炼、QA、AI 出题
-> 提交自测
-> 客观题本地评分，主观题 AI 评分
-> 错题自动沉淀
-> AI 根据错题和薄弱知识点生成复习计划
```

## 2. 实测通过项

| 模块 | 接口 | 结果 |
|---|---|---|
| 健康检查 | `GET /health` | 通过，返回 `status=ok` |
| 未登录访问 | `GET /materials` | 通过，返回 HTTP 401 |
| 注册 | `POST /auth/register` | 通过 |
| 登录 | `POST /auth/login` | 通过，返回 Bearer Token |
| 目标创建 | `POST /study-targets` | 通过 |
| TXT 上传 | `POST /materials` | 通过，初始 `parse_status=uploaded` |
| 未解析资料 QA | `POST /qa/ask` | 通过，返回 HTTP 409 |
| TXT 解析 | `POST /materials/{id}/parse` | 通过，变为 `parse_status=parsed` |
| TXT 预览 | `GET /materials/{id}/preview` | 通过，返回 `preview_text` |
| PDF 解析边界 | `POST /materials/{id}/parse` | 通过，返回 `parse_status=failed` 和 `parse_error` |
| 知识提炼 | `POST /knowledge/extract` | 通过 |
| AI 问答 | `POST /qa/ask` | 通过，真实模型调用 |
| QA 历史 | `GET /qa/history` | 通过 |
| AI 出题 | `POST /questions/generate` | 通过，生成客观题和主观题 |
| 自测提交 | `POST /tests/submit` | 通过 |
| 主观题 AI 评分 | `POST /tests/submit` | 通过，返回 `score/matched_points/missing_points/misconceptions` |
| 错题列表 | `GET /wrong-questions` | 通过 |
| 错题掌握状态 | `PATCH /wrong-questions/{id}/mastery` | 通过 |
| AI 复习计划 | `POST /review-plans/generate` | 通过，真实模型调用 |
| 复习计划列表 | `GET /review-plans` | 通过 |
| 跨用户资料访问 | `GET /materials/{id}` | 通过，返回资料不存在 |

## 3. 本次测试用例摘要

测试资料文本：

```text
需求分析用于明确系统边界、用户角色、功能范围和验收标准。
系统设计关注架构、模块划分和接口设计。
软件测试用于验证系统是否满足需求，常见方法包括单元测试、集成测试和验收测试。
错题复盘可以帮助发现薄弱知识点并安排后续复习。
```

关键实测 ID：

```text
target_id=3
material_id=4
pdf_id=5
objective_id=9
subjective_id=10
wrong_id=4
```

这些 ID 来自本地测试数据库，仅用于说明本次验收过程；其他环境中会不同。

## 4. 典型成功响应形态

### 4.1 TXT parse

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material": {
      "id": 4,
      "file_type": "txt",
      "parse_status": "parsed",
      "parse_error": null
    }
  }
}
```

### 4.2 PDF parse 当前边界

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "material": {
      "file_type": "pdf",
      "parse_status": "failed",
      "parse_error": "当前仅支持 TXT 资料解析，PDF 解析尚未接入"
    }
  }
}
```

说明：当前不会用 mock PDF/OCR 文本污染 AI 闭环。

### 4.3 QA

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "question": "需求分析和系统设计有什么区别？",
    "answer": "根据资料，需求分析用于明确系统边界、用户角色、功能范围和验收标准；系统设计关注架构、模块划分和接口设计。",
    "references": [
      {
        "material_id": 4,
        "snippet": "需求分析用于明确系统边界、用户角色、功能范围和验收标准"
      }
    ]
  }
}
```

### 4.4 自测结果

```json
{
  "test_record_id": 4,
  "score": 0.0,
  "accuracy": 0.0,
  "total_count": 2,
  "correct_count": 0,
  "wrong_count": 2,
  "results": [
    {
      "question_id": 10,
      "is_correct": false,
      "score": 0.0,
      "matched_points": [],
      "missing_points": ["单元测试目的", "集成测试目的", "验收测试目的", "测试执行顺序"],
      "misconceptions": ["混淆了需求分析/系统设计与测试方法的概念"]
    }
  ]
}
```

### 4.5 复习计划

```json
{
  "id": 3,
  "target_id": 3,
  "title": "软件工程期末复习 - 错题突击计划",
  "summary": "根据薄弱点，需求分析和软件测试安排每日任务。",
  "tasks": [
    {
      "date": "2026-06-12",
      "title": "需求分析核心突破",
      "material_id": 4,
      "wrong_question_id": 3,
      "completed": false
    }
  ]
}
```

## 5. 前端联调注意点

1. 登录后保存 `data.token.access_token`，之后所有业务请求放入：

```text
Authorization: Bearer <token>
```

2. 资料上传后不要直接启用 AI 功能，应先调用：

```text
POST /materials/{material_id}/parse
```

3. 前端应根据 `parse_status` 控制按钮：

```text
uploaded/parsing: 禁用 AI 功能
parsed: 允许知识提炼、QA、出题
failed: 显示 parse_error
```

4. 主观题提交用 `answer_text`，客观题提交用 `answer`：

```json
{
  "question_id": 10,
  "answer_text": "主观题答案"
}
```

```json
{
  "question_id": 9,
  "answer": ["A"]
}
```

5. 图片/PDF 作答字段已经预留：

```text
answer_file_ids
answer_file_urls
```

但 OCR 尚未接入，当前不要只传文件答案。

## 6. 后端协作注意点

1. `materials.parsed_text` 已成为 AI 闭环的资料入口。
2. TXT parse 已真实实现，PDF/OCR 后续应替换 `ParserService._extract_text()` 中的失败分支。
3. AI 模块通过 `material_access_service.get_material_for_ai()` 读取资料，要求 `parse_status == parsed`。
4. 复习计划已落库到 `review_plans` 和 `review_plan_tasks`。
5. 复习任务已有 `completed` 字段，但还没有任务完成接口，后续可补：

```text
PATCH /review-plans/tasks/{task_id}/complete
```

## 7. Review 关注点

当前后端已经完成可运行主闭环，但仍有以下边界：

- 知识提炼仍偏规则生成，未完全接入真实 AI。
- PDF 解析和图片 OCR 尚未接入。
- AI 调用日志目前主要在应用日志中，未持久化为 `ai_call_logs`。
- 复习计划任务完成状态尚未提供更新接口。
- AI 返回质量仍需要后续 Review 后调 prompt 和结构。