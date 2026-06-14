# AI 智能备考复习平台后端

基于 FastAPI + PostgreSQL + Redis 的后端服务。当前主分支功能已经形成学生端核心学习闭环：

```text
注册/登录
-> 创建课程/考试目标
-> 上传 TXT/PDF/图片资料
-> 解析为 materials.parsed_text
-> 知识提炼 / AI 问答 / AI 出题
-> 自测提交与评分
-> 错题沉淀
-> AI 生成复习计划
```

## 1. 启动

```bash
docker compose up --build -d
docker compose exec api alembic upgrade heads
```

接口地址：

```text
http://localhost:8000
```

Swagger 文档：

```text
http://localhost:8000/docs
```

健康检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/redis
```

首次启动或数据库重置后，需要执行数据库迁移。当前项目存在多个 Alembic head，建议使用 `heads`：

```bash
docker compose exec api alembic upgrade heads
```

## 当前接口测试流程

### 1. 注册学生账号

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "student1", "password": "123456", "display_name": "学生1"}'
```

### 2. 登录获取 Token

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "student1", "password": "123456"}'
```

复制响应中的 `data.token.access_token`，后续请求通过 Bearer Token 鉴权：

```bash
TOKEN='粘贴 access_token'
```

### 3. 创建课程/考试目标

```bash
curl -X POST http://localhost:8000/study-targets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "数据库系统期末复习",
    "subject": "数据库系统",
    "target_type": "exam",
    "exam_date": "2026-07-01",
    "review_goal": "掌握重点章节并完成错题复盘"
  }'
```

复制响应中的 `data.target.id`：

```bash
TARGET_ID='粘贴 target id'
```

### 4. 上传资料并进入后台解析

资料上传接口支持 TXT、PDF 和图片。默认 `auto_parse=true`，上传成功后会创建解析任务并立即返回 `parse_status=parsing`，后台任务完成后资料状态会更新为 `parsed` 或 `failed`。

```bash
curl -X POST http://localhost:8000/materials \
  -H "Authorization: Bearer $TOKEN" \
  -F "target_id=$TARGET_ID" \
  -F "file=@docs/temp/test_materials/test.txt"
```

如果只想上传但暂不解析，可以传：

```bash
-F "auto_parse=false"
```

### 5. 查看资料解析状态

```bash
curl "http://localhost:8000/materials?target_id=$TARGET_ID" \
  -H "Authorization: Bearer $TOKEN"
```

也可以查看单个资料详情：

```bash
curl http://localhost:8000/materials/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 6. 手动重新解析资料

如果资料解析失败，或上传时设置了 `auto_parse=false`，可以手动创建后台解析任务：

```bash
curl -X POST http://localhost:8000/materials/1/parse \
  -H "Authorization: Bearer $TOKEN"
```

该接口会立即返回 `parse_status=parsing`，实际解析在后台执行。

### 7. 预览资料

TXT 资料可以直接预览原始文本；PDF 和图片资料当前主要通过解析后的 `parsed_text` 供 AI 模块使用，预览接口会返回当前阶段的提示信息。

```bash
curl http://localhost:8000/materials/1/preview \
  -H "Authorization: Bearer $TOKEN"
```

## 文件解析策略

当前资料解析策略如下：

| 文件类型 | 处理方式 |
|---|---|
| TXT | 直接读取 UTF-8 文本内容 |
| 文本型 PDF | 优先使用 `pypdf` 提取页面文本 |
| 扫描版 PDF | 当 `pypdf` 未提取到文本时，使用 `pdf2image` 转图片，再通过 Tesseract OCR 识别 |
| 图片 | 使用 Tesseract OCR 识别文字 |

OCR 支持简体中文和英文混合识别，容器内安装了：

```text
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-chi-sim
poppler-utils
```

可以检查容器中的 OCR 语言包：

```bash
docker compose exec api tesseract --list-langs
```

应至少包含：

```text
chi_sim
eng
osd
```

## 管理员接口测试

注册接口默认创建学生账号。测试管理员接口时，可以先注册账号，再手动将角色改为 `admin`：

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "123456", "display_name": "管理员1"}'

docker compose exec postgres psql -U ai_study -d ai_study_db \
  -c "UPDATE users SET role = 'admin' WHERE username = 'admin1';"
```

登录管理员：

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin1", "password": "123456"}'
```

复制管理员 token：

```bash
ADMIN_TOKEN='粘贴管理员 access_token'
```

### 查看用户列表

```bash
curl http://localhost:8000/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 查看资料列表

```bash
curl http://localhost:8000/admin/materials \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 查看解析任务

```bash
curl http://localhost:8000/admin/tasks \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

按任务状态筛选：

```bash
curl "http://localhost:8000/admin/tasks?status=failed" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

任务状态包括：

```text
pending
running
succeeded
failed
```

### 重试解析任务

```bash
curl -X POST http://localhost:8000/admin/tasks/1/retry \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

这里的 `1` 是 `parse_tasks.id`，不是 `materials.id`。

### 查看管理员操作日志

```bash
curl http://localhost:8000/admin/logs \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

管理员重试解析任务时，会写入 `admin_logs`。

## AI 问答测试

资料解析完成后，可以基于真实 `materials.parsed_text` 调用 AI 问答：

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"material_id": 1, "question": "这份资料的主要内容是什么？"}'
```

如果资料仍处于 `uploaded`、`parsing` 或 `failed`，AI 接口会拒绝处理。

## 停止

```bash
docker compose down
```

如需清空数据库、Redis 和上传文件卷：

```bash
docker compose down -v
```

## 2. AI 配置

`.env.example` 提供了默认配置。Docker Compose 启动时会覆盖容器内的数据库和 Redis 地址，让 API 通过服务名 `postgres`、`redis` 连接。

真实 AI 调用请在本地 `.env` 中配置，且不要提交真实 API Key：

```text
AI_PROVIDER=openai-compatible
AI_API_KEY=你的 API Key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
AI_TIMEOUT_SECONDS=30
```

检查容器内配置时不要打印 `AI_API_KEY`：

```bash
docker compose exec api sh -lc 'printf "AI_PROVIDER=%s\nAI_BASE_URL=%s\nAI_MODEL=%s\n" "$AI_PROVIDER" "$AI_BASE_URL" "$AI_MODEL"'
```

真实 AI 调用日志：

```bash
docker compose logs -f api
```

可看到类似：

```text
AI call started task=qa ...
AI call started task=question_generation ...
AI call started task=subjective_scoring ...
AI call started task=wrong_reason_analysis ...
AI call started task=review_plan_generation ...
```

## 3. 完整联调流程

以下命令从注册开始，跑通完整闭环。命令依赖 `python3` 解析 JSON，不需要 `jq`。

### 3.1 注册

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "student_flow", "password": "123456", "display_name": "流程测试用户"}'
```

重复用户名会返回：

```json
{"code":40001,"message":"用户名已存在","data":null}
```

### 3.2 登录并保存 Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "student_flow", "password": "123456"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token']['access_token'])")
```

后续所有业务接口都需要：

```text
Authorization: Bearer $TOKEN
```

错误密码会返回：

```json
{"code":40002,"message":"用户名或密码错误","data":null}
```

未带 Token 会返回 HTTP 401：

```json
{"detail":"未提供认证令牌"}
```

### 3.3 创建学习目标

```bash
TARGET_ID=$(curl -s -X POST http://localhost:8000/study-targets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "软件工程期末复习",
    "subject": "软件工程",
    "target_type": "exam",
    "exam_date": "2026-06-30",
    "review_goal": "掌握需求分析、系统设计、测试和错题复盘"
  }' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['target']['id'])")
```

### 3.4 上传 TXT 资料

```bash
printf '需求分析用于明确系统边界、用户角色、功能范围和验收标准。系统设计关注架构、模块划分和接口设计。软件测试用于验证系统是否满足需求，常见方法包括单元测试、集成测试和验收测试。错题复盘可以帮助发现薄弱知识点并安排后续复习。' > /tmp/se_review.txt

MATERIAL_ID=$(curl -s -X POST http://localhost:8000/materials \
  -H "Authorization: Bearer $TOKEN" \
  -F "target_id=$TARGET_ID" \
  -F "file=@/tmp/se_review.txt;type=text/plain" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['material']['id'])")
```

上传后默认会创建后台解析任务，接口立即返回：

```text
parse_status=parsing
```

如果后台解析尚未完成，此时调用 AI 接口会返回 HTTP 409：

```json
{"detail":"Material is not parsed yet."}
```

### 3.5 查看解析结果

```bash
curl "http://localhost:8000/materials/$MATERIAL_ID" \
  -H "Authorization: Bearer $TOKEN"
```

成功后：

```text
parse_status=parsed
parse_error=null
```

如果上传时传了 `auto_parse=false`，或者需要重新解析，可以手动创建后台解析任务：

```bash
curl -X POST http://localhost:8000/materials/$MATERIAL_ID/parse \
  -H "Authorization: Bearer $TOKEN"
```

当前真实支持 TXT、文本型 PDF、扫描版 PDF 和图片 OCR。解析失败时会写入 `parse_error`，前端可以直接展示失败原因。

### 3.6 预览资料

```bash
curl "http://localhost:8000/materials/$MATERIAL_ID/preview" \
  -H "Authorization: Bearer $TOKEN"
```

TXT 会返回 `preview_text`。

### 3.7 知识提炼

```bash
curl -X POST http://localhost:8000/knowledge/extract \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"material_id\": $MATERIAL_ID, \"target_id\": $TARGET_ID}"
```

返回字段包括：

```text
summary
outline
keywords
key_points
exam_points
```

### 3.8 AI 问答

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"material_id\": $MATERIAL_ID, \"question\": \"需求分析和系统设计有什么区别？\"}"
```

QA 会真实调用 OpenAI-compatible 模型，并保存到 `qa_records`。

查看历史：

```bash
curl "http://localhost:8000/qa/history?material_id=$MATERIAL_ID&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.9 AI 生成题目

```bash
curl -X POST http://localhost:8000/questions/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"material_id\": $MATERIAL_ID,
    \"question_types\": [\"single_choice\", \"subjective\"],
    \"difficulty\": \"medium\",
    \"count\": 2
  }"
```

支持题型：

```text
single_choice
multiple_choice
true_false
subjective
```

客观题每个选项包含：

```json
{"key":"A","text":"...","analysis":"该选项为什么正确或错误"}
```

主观题：

```json
{
  "type": "subjective",
  "options": [],
  "correct_answer": ["参考答案或评分要点"],
  "analysis": "评分要点"
}
```

### 3.10 提交自测

把上一步返回的题目 ID 填入：

```bash
curl -X POST http://localhost:8000/tests/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"material_id\": $MATERIAL_ID,
    \"target_id\": $TARGET_ID,
    \"answers\": [
      {\"question_id\": 客观题ID, \"answer\": [\"A\"]},
      {
        \"question_id\": 主观题ID,
        \"answer_text\": \"需求分析主要明确用户需求和系统边界，系统设计主要考虑架构、模块和接口。\"
      }
    ]
  }"
```

评分逻辑：

- 客观题：本地按正确答案判分。
- 主观题：真实 AI 评分。
- 错题：自动写入 `wrong_questions`。

主观题结果包含：

```text
score
matched_points
missing_points
misconceptions
analysis
```

### 3.11 错题本

```bash
curl "http://localhost:8000/wrong-questions?target_id=$TARGET_ID&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

更新掌握状态：

```bash
curl -X PATCH http://localhost:8000/wrong-questions/错题ID/mastery \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"mastery_status": "reviewing"}'
```

状态枚举：

```text
unmastered
reviewing
mastered
```

### 3.12 AI 生成复习计划

```bash
curl -X POST http://localhost:8000/review-plans/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"target_id\": $TARGET_ID,
    \"start_date\": \"2026-06-12\",
    \"end_date\": \"2026-06-14\"
  }"
```

真实 AI 会根据目标、错题和薄弱知识点生成每日任务。返回：

```text
title
summary
tasks[].date
tasks[].title
tasks[].content
tasks[].material_id
tasks[].wrong_question_id
tasks[].completed
```

查询计划：

```bash
curl "http://localhost:8000/review-plans?target_id=$TARGET_ID&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

非法日期会返回 HTTP 400：

```json
{"detail":"end_date cannot be earlier than start_date"}
```

## 4. 已验证结果

本地已在 Docker 环境完成一次完整验收：

```text
用户注册/登录：通过
学习目标创建：通过
TXT 上传：通过
异步解析任务：通过，parse_status 从 parsing 更新为 parsed 或 failed
未解析资料调用 QA：HTTP 409，符合预期
TXT parse：通过，parse_status=parsed
文本型 PDF parse：通过，parse_status=parsed
图片 OCR：通过，识别失败时返回明确 parse_error
知识提炼：通过
QA：通过，真实模型调用，记录保存
QA history：通过
AI 出题：通过，返回客观题和主观题
自测提交：通过，客观题本地判分，主观题 AI 评分
错题沉淀：通过
错题掌握状态更新：通过
AI 复习计划生成：通过
复习计划列表：通过
跨用户资料访问：返回资料不存在，隔离通过
```

## 5. 当前能力边界

- TXT 资料解析已真实实现。
- 文本型 PDF 通过 `pypdf` 提取文本。
- 扫描版 PDF 通过 `pdf2image` 转图片后使用 Tesseract OCR 识别。
- 图片资料通过 Tesseract OCR 识别，支持简体中文和英文。
- 知识提炼目前是规则结构化生成，适合前端展示和闭环联调。
- QA、出题、主观题评分、客观题错因分析、复习计划生成已接入 OpenAI-compatible 模型。
- 复习任务有 `completed` 字段，但暂未实现任务完成状态更新接口。

## 6. 给前端的调用顺序

前端主流程建议：

```text
POST /auth/register
POST /auth/login
POST /study-targets
POST /materials
POST /materials/{id}/parse
GET /materials/{id}
POST /knowledge/extract
POST /qa/ask
GET /qa/history
POST /questions/generate
POST /tests/submit
GET /wrong-questions
PATCH /wrong-questions/{id}/mastery
POST /review-plans/generate
GET /review-plans
```

页面上应根据 `parse_status` 控制 AI 功能按钮：

```text
uploaded/parsing: 禁用知识提炼、QA、出题
parsed: 允许调用 AI 学习接口
failed: 展示 parse_error
```
