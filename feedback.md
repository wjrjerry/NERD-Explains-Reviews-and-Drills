# main 分支前后端实现反馈

本文基于当前 `main` 分支代码进行分析，重点检查前端是否已经实现后端提供的核心功能、当前学习闭环是否完整，以及后续仍需补齐的接口和交互。

## 1. 总体结论

当前 `main` 已经从“单资料 AI 学习闭环”推进到一个较完整的全栈版本。后端提供了认证、学习目标、资料上传与解析、结构化资料、知识提炼、知识图谱、AI 问答、AI 出题、自测、错题、复习计划、导出、AI 用量和管理员接口；前端已经接入其中大部分学生端核心能力。

当前前端已经覆盖：

- 注册、登录、token 保存与自动会话恢复
- 学习目标创建、列表、更新、删除
- 资料上传、资料列表、解析状态展示、解析触发、删除
- 资料预览与结构化阅读
- 资料级知识提炼
- 目标级知识图谱生成、展示、知识点详情
- 基于资料的 AI 问答与历史展示
- 基于资料的 AI 出题，支持单选、多选、判断、主观题
- 自测提交、结果展示、主观题反馈展示
- 错题本、错题掌握状态更新、错题 Markdown 导出
- 复习计划生成、展示、Markdown 导出
- 知识总结 Markdown 导出、Anki CSV 导出
- 学习仪表盘与基础管理员健康检查

当前仍未充分覆盖：

- AI 用量统计页面
- 管理员端真实数据管理页面
- 知识点详情接口的深度交互
- 题目/错题与真实知识点 ID 的稳定绑定
- 测试后自动更新知识点掌握度的完整闭环
- 前端对自动解析、自动知识提炼、自动图谱刷新的状态感知
- 目标级 QA / 按知识点 QA
- 按知识点出题与用户自定义出题要求
- 资料解析任务队列的前端展示
- OCR/PDF 解析质量、失败原因和重试的完整用户体验

## 2. 当前运行与构建状态

当前 `main` 分支已通过以下检查：

```text
前端构建：npm run build 通过
后端编译：python -m compileall app 通过
当前分支：main...origin/main
```

推荐运行方式：

```bash
docker compose up --build -d
docker compose exec api alembic upgrade heads

cd frontend
npm install
npm run dev
```

访问地址：

```text
前端：http://127.0.0.1:5173/
后端：http://localhost:8000
Swagger：http://localhost:8000/docs
```

## 3. 前端对后端接口覆盖情况

| 后端模块 | 后端接口 | 前端实现情况 | 反馈 |
|---|---|---|---|
| 健康检查 | `GET /health`, `/health/db`, `/health/redis` | 已接入 | 管理员页展示 API、数据库、Redis 状态 |
| 认证 | `POST /auth/register`, `POST /auth/login`, `GET /users/me` | 已接入 | 支持注册、登录、本地 token 保存、会话恢复 |
| 学习目标 | `POST/GET/PATCH/DELETE /study-targets` | 已接入 | 支持目标管理；尚未做复杂筛选和排序 |
| 目标资料块 | `GET /study-targets/{target_id}/chunks` | 未直接接入 | 可用于目标级阅读、目标级 QA 检索，前端暂未使用 |
| 资料上传 | `POST /materials` | 已接入 | 支持 PDF/TXT/图片上传入口 |
| 资料列表/详情 | `GET /materials`, `GET /materials/{id}` | 已接入 | 支持资料库和详情页 |
| 资料预览 | `GET /materials/{id}/preview` | 已接入 | 详情页展示 `preview_text` |
| 资料结构化 | `GET /materials/{id}/structured` | 已接入 | 详情页已有章节与 chunks 阅读器 |
| 资料 sections/chunks | `GET /materials/{id}/sections`, `/chunks` | 间接覆盖 | 前端使用 `/structured` 一次性获取，没有单独分页/筛选 |
| 资料解析 | `POST /materials/{id}/parse` | 已接入 | 前端可手动触发解析；解析状态和错误会展示 |
| 自动解析 | `POST /materials` 默认 `auto_parse=true` | 后端已实现，前端提示不准确 | 上传后会自动进入后台解析，但前端仍提示“请先解析资料”，且没有轮询解析状态 |
| 知识提炼 | `POST /knowledge/extract` | 已接入 | 当前只发送 `material_id`，已符合后端接口约束 |
| 自动知识提炼 | 解析成功后后台调用 `run_after_material_parsed` | 后端已实现，前端无提示 | 自动资料级/目标级提炼可能已入库，但前端不会自动展示提炼状态或结果 |
| 知识图谱 | `GET /knowledge-graphs/{target_id}` | 已接入 | 进入目标后自动尝试加载图谱 |
| 图谱生成 | `POST /knowledge-graphs/generate` | 已接入 | 可手动生成/刷新图谱 |
| 知识点资料 | `GET /knowledge-points/{id}/materials` | 未接入 | 当前图谱节点只展示 graph response 内的 materials |
| 知识点题目 | `GET /knowledge-points/{id}/questions` | 未接入 | 点击知识点后未展示对应题目列表 |
| 知识点错题 | `GET /knowledge-points/{id}/wrong-questions` | 未接入 | 当前用前端名称匹配错题，准确度有限 |
| 知识点掌握度 | `PATCH /knowledge-points/{id}/mastery` | 未接入 | 暂不支持手动调整知识点掌握度；自动掌握度依赖题目先绑定真实 `knowledge_point_id` |
| AI 问答 | `POST /qa/ask`, `GET /qa/history` | 已接入 | 仍以 `material_id` 为中心，尚未做目标级/知识点级问答 |
| AI 出题 | `POST /questions/generate` | 已接入 | 支持题型、难度、数量；当前前端按 `material_id` 出题，通常不会绑定图谱知识点 ID |
| 自测 | `POST /tests/submit` | 已接入 | 支持客观题和主观题提交；掌握度更新只在题目存在 `question_knowledge_points` 关联时生效 |
| 测试记录 | `GET /tests/records` | 已接入 | 仪表盘用于计算近期自测均分 |
| 错题 | `GET /wrong-questions`, `PATCH /wrong-questions/{id}/mastery` | 已接入 | 支持错题展示和掌握状态更新 |
| 复习计划 | `POST /review-plans/generate`, `GET /review-plans` | 已接入 | 支持计划生成、列表和任务展示 |
| 导出 | `/exports/*.md`, `/exports/anki/*.csv` | 已接入 | 支持错题、复习计划、知识总结、Anki 导出 |
| AI 用量 | `GET /ai-usage/summary`, `/logs` | 未接入 | 后端已有，前端暂无页面 |
| 管理员 | `/admin/users`, `/admin/materials`, `/admin/tasks`, `/admin/logs` | 基本未接入 | 前端仅展示健康检查和当前用户资料巡检，不是真正管理员端 |

## 4. 当前前端页面实现情况

### 4.1 登录与会话

前端通过 `localStorage` 保存 `ai_review_token`，后续请求自动加入：

```text
Authorization: Bearer <token>
```

登录态恢复时会调用 `GET /users/me`，失败则清除 token。

评价：实现合理，满足当前前后端联调需要。后续若要更接近生产环境，可补充 token 过期提示、刷新机制和退出确认。

### 4.2 仪表盘

仪表盘目前聚合：

- 学习目标数量
- 资料总数
- 已解析资料数量
- 解析失败资料数量
- 资料解析状态条
- 知识图谱掌握度点阵
- 近期自测均分
- 错题总数
- 即将复习任务

评价：已经覆盖学习平台首页的核心概览。缺口是 AI 用量、近 7 天学习趋势、按知识点/题型正确率等更细粒度统计尚未展示。

### 4.3 资料库与资料详情

前端支持上传 PDF/TXT/图片，调用 `POST /materials` 入库，并可调用 `POST /materials/{id}/parse` 触发解析。

需要注意：当前后端上传接口默认 `auto_parse=true`，也就是说前端上传资料后，后端会立即创建后台解析任务，并把资料状态置为 `parsing`。因此前端当前上传成功后的提示：

```text
资料上传成功，请先解析资料再使用 AI 学习功能。
```

已经和后端真实流程不一致。更准确的提示应为：

```text
资料上传成功，已开始后台解析，请稍后查看解析状态。
```

当前前端也没有针对 `parse_status=parsing` 的自动轮询。结果是：即使后端后台解析已经完成，页面仍可能停留在旧状态，用户需要手动刷新接口数据或重新进入资料详情才能看到 `parsed/failed`。

详情页展示：

- 资料基本信息
- 解析状态
- `parse_error`
- 文本预览
- 结构化章节与 chunks
- 知识提炼结果
- 生成图谱、导出总结、进入 QA、进入出题入口

评价：资料主流程已可用。需要注意，前端文案写的是“PDF / TXT / 图片资料”，但如果当前环境 OCR/Tesseract/poppler 或 PDF 内容质量不满足要求，PDF/图片仍可能解析失败。建议前端在上传区增加能力说明：TXT 最稳定，PDF/图片依赖 OCR，失败时查看 `parse_error`。

PDF 解析失败的常见原因包括：

- Docker 镜像未重新 build，容器里缺少 `poppler-utils`、`tesseract-ocr` 或中文语言包。
- PDF 是扫描版，OCR 识别不到足够可用文本。
- PDF 页数超过 `PDF_OCR_MAX_PAGES`，后续页未处理。
- OCR 超时，受 `OCR_TIMEOUT_SECONDS` 影响。
- PDF 文件损坏、加密、图片质量低或文字过小。

排查时建议查看：

```sql
SELECT id, original_filename, file_type, parse_status, parse_error, parse_warning
FROM materials
ORDER BY id DESC
LIMIT 10;

SELECT id, material_id, status, failure_reason, started_at, finished_at
FROM parse_tasks
ORDER BY id DESC
LIMIT 10;
```

### 4.4 知识提炼

前端调用：

```json
{
  "material_id": 1
}
```

这与当前后端 `POST /knowledge/extract` 约束一致。知识提炼结果展示 summary、outline、keywords、key_points、exam_points。

评价：资料级知识提炼已接入。目标级自动提炼/汇总结果目前更多体现在知识图谱和导出总结中，前端还没有单独的“目标级知识提炼面板”。

后端实际上还存在一条自动知识提炼链路：

```text
资料解析成功
-> run_after_material_parsed()
-> 资料级知识提炼
-> 目标级知识提炼
-> 目标级知识图谱刷新
```

但前端没有展示这条后台链路的状态。当前 `knowledge` 结果只会在用户手动点击“知识提炼”后写入页面状态；如果后台自动提炼已经完成，前端也不会自动读取最新结果。因此用户会看到“解析成功了，但知识提炼结果仍然为空”，这属于前端状态同步缺失，不一定代表后端没有生成。

建议前端在资料解析成功后自动刷新：

```text
GET /materials/{id}
GET /materials/{id}/structured
GET /knowledge-graphs/{target_id}
```

并考虑补充一个“最新知识提炼结果查询接口”或在现有 `POST /knowledge/extract` 上明确支持 `force_regenerate=false` 的查询/复用语义，避免为了展示结果重复调用 AI。

### 4.5 知识图谱

前端已实现“知识图谱”页面：

- `GET /knowledge-graphs/{target_id}` 自动加载
- `POST /knowledge-graphs/generate` 手动生成/刷新
- 节点大小根据 `importance_weight` 映射
- 节点颜色根据 `mastery_status` 映射
- 节点详情展示掌握度、正确率、错题数、作答数、关联资料片段
- 通过错题中的 `knowledge_points` 名称做前端匹配，展示关联错题

评价：满足知识图谱的第一版可视化要求，已经能表达“重要程度”和“掌握情况”。但当前错题关联是前端字符串匹配，不如调用 `GET /knowledge-points/{id}/wrong-questions` 精确；知识点资料和题目也没有调用后端详情接口。

### 4.5.1 掌握度更新链路

当前掌握度不是简单由“是否有错题”直接计算出来，而是依赖题目、错题和知识点之间的真实 ID 关联。完整链路应为：

```text
目标 target
-> 资料 material
-> 解析后生成知识点 knowledge_points
-> 出题时题目绑定 question_knowledge_points
-> 用户提交测试 tests/submit
-> test_service 根据 question_knowledge_points 得到 knowledge_point_ids
-> 写入 wrong_questions
-> 写入 wrong_question_knowledge_points
-> 更新 user_knowledge_mastery
-> GET /knowledge-graphs/{target_id} 返回 mastery_score / accuracy / wrong_count
-> 前端知识图谱显示颜色、正确率、掌握度
```

当前代码中掌握度更新函数已经存在：

```text
app/services/knowledge_mastery_service.py
```

测试提交时也会尝试调用：

```text
knowledge_mastery_service.update_mastery_after_test(...)
```

但它有一个关键前提：提交的题目必须能查到 `question_knowledge_points` 关联。如果用户当前是从前端“按资料出题”，请求体只有：

```json
{
  "material_id": 1,
  "question_types": ["single_choice"],
  "difficulty": "medium",
  "count": 5
}
```

这种路径下，后端通常只会保存题目的字符串知识点：

```text
questions.knowledge_points = ["需求分析", "系统设计"]
```

但不会稳定写入真实图谱节点关联：

```text
question_knowledge_points.question_id
question_knowledge_points.knowledge_point_id
```

因此测试提交时：

```text
linked_point_ids = []
mastery_outcomes = []
```

最终结果就是：

```text
wrong_questions 有错题
questions.knowledge_points 有文字标签
question_knowledge_points 为空
wrong_question_knowledge_points 为空
user_knowledge_mastery 不更新
知识图谱 mastery_score / accuracy / wrong_count 仍为 0
```

所以“有一道错题，但掌握度全为 0”不是前端显示错误，而是当前题目/错题没有和真实知识点 ID 形成闭环。

### 4.6 QA 问答

当前 QA 仍基于单个资料：

```json
{
  "material_id": 1,
  "question": "..."
}
```

评价：资料级问答可用，但与“目标为中心、可选择知识点提问”的最终设想还有差距。后续建议支持：

- 目标级 QA：基于一个 target 下多个资料回答
- 知识点级 QA：围绕某个 knowledge_point 回答
- 问题附加上下文：允许用户指定“请用例题解释/请按考试答题方式回答”

### 4.7 AI 出题与自测

前端已支持：

- 题型选择：单选、多选、判断、主观题
- 难度选择：easy/medium/hard
- 题目数量
- 客观题点击选项作答
- 主观题文本作答
- 提交后展示得分、正确率、解析、覆盖要点、缺失要点、误区

评价：自测闭环已基本完成。缺口是前端暂未支持：

- 选择知识点出题
- 用户自定义出题要求
- 基于当前章节/chunk 出题
- 图片/PDF 作答上传

另外，当前前端出题仍以 `material_id` 为中心，这会影响掌握度闭环。后端其实已经支持更合理的目标级/知识点级出题参数：

```json
{
  "target_id": 1,
  "knowledge_point_ids": [3, 5],
  "question_types": ["single_choice", "subjective"],
  "difficulty": "medium",
  "count": 5,
  "extra_requirement": "更偏期末考试概念辨析"
}
```

当前前端尚未提供知识点选择和 `extra_requirement` 输入框，因此用户实际产生的题目很可能没有真实 `knowledge_point_id` 绑定，后续自测也无法更新 `user_knowledge_mastery`。

### 4.8 错题本

前端已支持：

- 错题列表展示
- 展示知识点、用户答案、正确答案、错因、解析
- 切换 `unmastered/reviewing/mastered`
- 导出错题 Markdown

评价：错题列表闭环可用。后续建议增加按知识点、目标、资料、掌握状态筛选，以及从知识图谱节点跳转到精确错题列表。

需要特别区分两类掌握状态：

```text
wrong_questions.mastery_status
```

这是“单道错题”的掌握状态，前端当前已经支持手动切换 `unmastered/reviewing/mastered`。

```text
user_knowledge_mastery.mastery_status
```

这是“知识点”的掌握状态，用于知识图谱颜色、正确率、薄弱点复习计划等。它不会因为错题列表里出现一条错题就自动变化，必须有 `question_knowledge_points` / `wrong_question_knowledge_points` 这样的真实知识点 ID 关联。

### 4.9 复习计划

前端已支持：

- 按目标、起止日期生成复习计划
- 计划列表展示
- 任务列表展示
- 导出计划 Markdown

评价：满足基础复习计划展示。缺口是任务完成状态没有前端交互接口，用户不能在页面中标记任务已完成。

### 4.10 导出

前端已接入：

- 错题本 Markdown
- 复习计划 Markdown
- 知识总结 Markdown
- Anki CSV

评价：导出功能对用户有实际价值，已覆盖 P1 要求。后续可以增加导出按钮的 loading 状态和空数据提示。

### 4.11 管理员端

当前前端“管理员端”主要展示：

- API 健康
- 数据库健康
- Redis 健康
- 当前用户资料总数
- 当前用户资料解析巡检

但后端真实管理员接口包括：

- `GET /admin/users`
- `GET /admin/materials`
- `GET /admin/tasks`
- `POST /admin/tasks/{task_id}/retry`
- `GET /admin/logs`

这些目前没有接入。

评价：当前管理员端更像“系统健康检查面板”，还不是完整管理员运维中心。若需要验收管理员功能，需要继续扩展。

### 4.12 AI 用量与计费

后端已有：

- `GET /ai-usage/summary`
- `GET /ai-usage/logs`

前端当前没有页面展示 token 消耗、调用次数、估算费用、按功能统计、调用日志。

评价：这是 P1 中“用户可查看计费情况”的主要缺口。建议新增“AI 用量”页面或放入仪表盘/管理员页。

## 5. 当前主要问题与风险

### P0：前端仍有部分体验与后端能力不匹配

上传区写明支持 PDF/TXT/图片，但 PDF/图片解析依赖 OCR 环境和文件质量。若解析失败，用户可能认为是前端或系统错误。

建议：

- 上传区补充说明：TXT 最稳定，PDF/图片会尝试 OCR。
- 解析失败时显示更具体的 `parse_error` 和建议操作。
- 对扫描 PDF、大文件 PDF 增加提示。

### P0：自动解析流程前端没有状态同步

后端上传接口默认会自动解析：

```text
POST /materials
auto_parse=true
-> parse_status=parsing
-> BackgroundTasks 解析
```

但前端当前仍把上传和解析表现成完全手动流程，且没有轮询 `parsing` 状态。这会导致两个问题：

```text
用户以为需要手动点“解析”
用户看不到后台解析完成或失败的即时结果
```

建议：

1. 上传成功文案改为“已开始后台解析”。
2. 对 `parse_status=parsing` 的资料每 2-3 秒轮询 `GET /materials/{id}`。
3. 状态变为 `parsed` 后自动刷新 preview、structured、knowledge graph。
4. 状态变为 `failed` 后展示 `parse_error` 和 `parse_warning`。
5. 前端 `Material` 类型补充 `parse_warning?: string | null`。

### P0：自动知识提炼缺少用户可见反馈

后端解析成功后会尝试自动执行：

```text
资料级知识提炼
目标级知识提炼
知识图谱刷新
```

但前端没有对应状态，也不会自动展示后台生成的知识提炼结果。用户只能看到手动“知识提炼”按钮，因此容易误解为后端没有执行自动提炼。

建议：

- 解析成功后提示“正在同步知识提炼与图谱”。
- 解析成功后自动刷新图谱。
- 补充知识提炼历史/最新结果查询能力，或让前端以非强制方式调用 `/knowledge/extract` 获取已有结果。
- 自动提炼失败时不要影响资料解析成功，但应在前端可见，例如展示“资料解析成功，知识提炼待重试”。

### P0：知识图谱错题关联不够精确

当前知识图谱详情中“关联错题”通过前端字符串匹配：

```text
wrong_question.knowledge_points 与 activeNode.name 互相 includes
```

这会出现漏匹配或误匹配。

建议改为调用：

```text
GET /knowledge-points/{knowledge_point_id}/wrong-questions
```

### P0：掌握度闭环尚未完整打通

当前已经有：

```text
knowledge_points
user_knowledge_mastery
question_knowledge_points
wrong_question_knowledge_points
knowledge_mastery_service.update_mastery_after_test()
```

但前端主要使用“按资料出题”，导致题目通常只带字符串知识点，而没有绑定真实 `knowledge_point_id`。一旦 `question_knowledge_points` 为空，后续就无法更新 `user_knowledge_mastery`。

典型现象：

```text
错题本里有错题
知识图谱节点仍显示 0%
accuracy = 0
answered_count = 0
wrong_count = 0
```

推荐修复：

1. 后端增强按资料出题兜底逻辑：即使请求只传 `material_id`，也应根据 `material.target_id` 找到目标图谱，并用 AI/规则把题目绑定到最相关的 `knowledge_point_id`。
2. 前端增强出题入口：支持从知识图谱选择知识点出题，请求中传 `target_id` 和 `knowledge_point_ids`。
3. 前端提交测试后刷新知识图谱，确保最新 `user_knowledge_mastery` 反映到节点颜色和掌握度。
4. 知识图谱详情页不要用字符串匹配错题，应调用 `GET /knowledge-points/{id}/wrong-questions`。

调试时建议依次检查：

```sql
SELECT id, stem, knowledge_points FROM questions ORDER BY id DESC LIMIT 5;
SELECT * FROM question_knowledge_points ORDER BY id DESC LIMIT 10;
SELECT * FROM wrong_question_knowledge_points ORDER BY id DESC LIMIT 10;
SELECT knowledge_point_id, mastery_status, mastery_score, accuracy, answered_count, wrong_count
FROM user_knowledge_mastery
ORDER BY knowledge_point_id;
```

### P1：AI 用量页面缺失

后端已经完成 token 统计和本地估算计费，但前端没有入口。

建议新增页面：

```text
AI 用量
├── 总调用次数
├── prompt_tokens
├── completion_tokens
├── total_tokens
├── estimated_cost
├── 按 feature 分组
└── 最近调用日志
```

### P1：目标级学习链路仍不够强

当前 QA、出题、自测仍以 `material_id` 为中心。知识图谱引入后，用户更自然的路径应该是：

```text
选择目标
-> 查看知识图谱
-> 点击知识点
-> 查看关联资料/错题/题目
-> 针对该知识点提问或出题
```

前端目前只完成了图谱展示，未完成知识点 drill 链路。

### P1：出题缺少用户自定义要求

后端曾讨论过“用户自主输入补充题目要求”，当前前端出题表单只有题型、难度、数量。

建议增加：

```text
custom_instruction: string
```

例如：

```text
“更偏期末考试风格”
“多考概念辨析”
“围绕第三章知识点”
```

### P2：管理员端仍偏弱

后端管理员接口比较完整，但前端没有接入真实管理员数据。建议增加：

- 用户列表
- 全部资料列表
- 解析任务队列
- 失败任务重试
- 管理员日志
- AI 调用日志入口

### P2：结构化阅读还可以继续增强

当前已展示 sections/chunks，但还没有：

- 章节搜索
- 点击 chunk 生成题目
- 点击 chunk 提问
- chunk 与知识点的关联展示

## 6. 推荐下一步开发顺序

### 第一步：修复掌握度完整闭环

优先级最高，因为它直接影响知识图谱是否可信。如果用户做错题后图谱仍然全为 0，知识图谱会变成静态展示，而不是学习反馈系统。

后端建议：

```text
material_id 出题
-> 自动读取 material.target_id
-> 查找该目标下 knowledge_points
-> 根据题干、解析、AI 返回的 knowledge_points 字符串推断 knowledge_point_ids
-> 写入 question_knowledge_points
-> 测试提交时更新 user_knowledge_mastery
```

前端建议：

```text
知识图谱节点
-> 选择一个或多个知识点
-> 生成针对这些知识点的题
-> 提交测试后刷新图谱
```

### 第二步：补齐 AI 用量页面

优先级高，因为后端已完成，前端实现成本低，且能体现真实 AI 系统可观测性。

接入接口：

```text
GET /ai-usage/summary
GET /ai-usage/logs
```

### 第三步：完善知识点详情链路

把知识图谱从“展示图”升级成“学习入口”。

接入接口：

```text
GET /knowledge-points/{id}/materials
GET /knowledge-points/{id}/questions
GET /knowledge-points/{id}/wrong-questions
PATCH /knowledge-points/{id}/mastery
```

### 第四步：增强出题参数

让前端支持：

- 选择知识点出题
- 输入自定义要求
- 从当前章节/chunk 出题

### 第五步：目标级 QA

当前资料级 QA 可用，但目标级 QA 更贴合“一个复习目标下多个资料”的产品逻辑。

### 第六步：管理员端真实接入

接入：

```text
GET /admin/users
GET /admin/materials
GET /admin/tasks
POST /admin/tasks/{id}/retry
GET /admin/logs
```

## 7. 验收视角总结

当前 `main` 分支已经可以作为“完整学习闭环演示版本”：

```text
注册/登录
-> 创建目标
-> 上传资料
-> 解析资料
-> 查看结构化资料
-> 知识提炼
-> 生成知识图谱
-> AI 问答
-> AI 出题
-> 自测提交
-> 错题沉淀
-> 复习计划
-> 导出资料
```

但如果以“知识图谱驱动的目标级学习平台”为最终目标，当前前端还只是完成了图谱入口和核心闭环，尚未完全把 QA、出题、错题、复习计划都围绕知识点重新组织。下一阶段应围绕“知识点详情页”和“AI 用量页”继续补齐。
