# AI 智能备考复习平台后端

基于 FastAPI + PostgreSQL + Redis 的后端服务。当前主分支功能已经形成学生端核心学习闭环：

```text
注册/登录
-> 创建课程/考试目标
-> 上传 TXT 资料
-> 解析为 materials.parsed_text
-> 知识提炼 / AI 问答 / AI 出题
-> 自测提交与评分
-> 错题沉淀
-> AI 生成复习计划
```

## 1. 启动

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
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

停止服务：

```bash
docker compose down
```

如需清空数据库、Redis 和上传文件卷：

```bash
docker compose down -v
```

## 2. AI 配置

`.env.example` 提供默认配置。真实 AI 调用请在本地 `.env` 中配置，不要提交真实 API Key。

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

上传后资料状态是：

```text
parse_status=uploaded
```

此时调用 AI 接口会返回 HTTP 409：

```json
{"detail":"Material is not parsed yet."}
```

### 3.5 解析 TXT 资料

```bash
curl -X POST http://localhost:8000/materials/$MATERIAL_ID/parse \
  -H "Authorization: Bearer $TOKEN"
```

成功后：

```text
parse_status=parsed
parse_error=null
```

当前真实支持 TXT 解析。PDF/图片上传可以成功，但解析会变为 `failed`：

```text
parse_error=当前仅支持 TXT 资料解析，PDF 解析尚未接入
parse_error=当前仅支持 TXT 资料解析，图片 OCR 尚未接入
```

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
未解析资料调用 QA：HTTP 409，符合预期
TXT parse：通过，parse_status=parsed
PDF parse：返回 parse_status=failed，符合当前能力边界
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
- PDF 解析和图片 OCR 尚未接入真实服务，不会写入 mock 文本。
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
