# 后期 Review 后端 TODO（成员 B）

本文档只整理成员 B 相关的后期后端任务，聚焦 AI 学习闭环：

```text
知识点图谱 -> AI 出题 -> 自测评分 -> 错题归因 -> 掌握度更新 -> 复习计划 -> 导出
```

不纳入本文档的任务：

- 资料上传、资料解析、OCR、PDF 结构化解析：交由成员 A。
- 管理员端运维中心、解析任务队列、失败任务重试：交由成员 A。
- 前端知识图谱可视化布局：后端只提供节点、权重、错率和关联数据。

当前 B 侧已有基础链路偏向“单个资料”：

```text
materials.parsed_text
-> knowledge / qa / questions
-> tests
-> wrong_questions
-> review_plans
```

后续推荐调整为“学习目标中心”：

```text
study_target
-> materials
-> knowledge_points
-> qa / questions / tests / wrong_questions / review_plans
```

也就是说，一个复习目标下可以有多份资料，AI 基于这些资料生成一组目标级知识点。之后提问、出题、自测、错题和复习计划都优先围绕知识点组织，而不是固定绑定到某一份资料。

资料仍然重要，但它更像“知识点证据来源”：

```text
target 下的多个 material
-> 提供 parsed_text
-> 共同支撑 knowledge_points
-> 每个 knowledge_point 可关联一个或多个 material 片段
```

这样系统才能知道“用户在哪些知识点强、哪些知识点弱”，而不是只知道“用户问过哪份资料、做错了哪些题”。

## P0：知识点图谱与掌握度模型

### 目标

为每个学习目标生成知识点图谱，并把题目、问答、错题、自测结果、复习计划绑定到具体知识点上。

例如一个“操作系统”学习目标可以拆成：

```text
操作系统
├── 进程与线程
├── 调度算法
├── 死锁
├── 虚拟内存
├── 页面置换
└── 文件系统
```

每个知识块需要维护：

- 重要程度：由 AI 输出权重，映射为前端圆点大小。
- 掌握状态：未学习、薄弱、基本掌握、熟练。
- 错题表现：错率高显示红色，错率低显示绿色。
- 关联内容：点击知识块可查看关联题目和错题。

### 推荐新增表

#### `knowledge_points`

存储学习目标下的知识点图谱节点。

建议字段：

- `id`
- `user_id`
- `target_id`
- `parent_id`
- `name`
- `description`
- `importance_weight`
- `level`
- `sort_order`
- `source`
- `created_at`
- `updated_at`

说明：

- `target_id` 表示该知识点属于哪个复习目标。
- `parent_id` 支持树形结构。
- `importance_weight` 由 AI 输出，供前端映射圆点大小。
- `source` 可记录 `ai_generated`、`manual`、`material_extracted`。

#### `question_knowledge_points`

建立题目与知识点的多对多关系。

建议字段：

- `id`
- `question_id`
- `knowledge_point_id`
- `relevance_score`
- `created_at`

#### `material_knowledge_points`

建立资料与知识点的多对多关系。该表不负责资料解析，只记录 B 侧 AI 生成知识图谱后，某个知识点由哪些资料内容支撑。

建议字段：

- `id`
- `material_id`
- `knowledge_point_id`
- `relevance_score`
- `evidence_text`
- `created_at`

说明：

- `material_id` 来自成员 A 的资料模块。
- `evidence_text` 可保存该知识点对应的资料片段，便于 QA 和出题引用来源。
- 一个知识点可以来自多份资料，一份资料也可以支撑多个知识点。

#### `qa_knowledge_points`

建立问答记录与知识点的关系。

建议字段：

- `id`
- `qa_record_id`
- `knowledge_point_id`
- `relevance_score`
- `created_at`

#### `wrong_question_knowledge_points`

如错题与题目的知识点关系不完全一致，可增加错题级别关系表。

建议字段：

- `id`
- `wrong_question_id`
- `knowledge_point_id`
- `wrong_reason`
- `created_at`

#### `user_knowledge_mastery`

存储用户对每个知识点的掌握度。

建议字段：

- `id`
- `user_id`
- `target_id`
- `knowledge_point_id`
- `mastery_status`
- `mastery_score`
- `accuracy`
- `answered_count`
- `wrong_count`
- `last_practiced_at`
- `next_review_at`
- `created_at`
- `updated_at`

掌握状态建议枚举：

```text
unlearned
weak
basic
proficient
```

### 推荐新增接口

- `POST /knowledge-graphs/generate`
  - 输入：`target_id`
  - 行为：基于目标下已解析资料文本调用 AI 生成目标级知识点图谱。
  - 输出：知识点树、权重、说明。

- `GET /knowledge-graphs/{target_id}`
  - 输出：目标对应的知识图谱节点、重要程度、掌握状态、错率。

- [x] `GET /knowledge-points/{knowledge_point_id}/wrong-questions`
  - 输出：该知识点关联错题列表。

- [x] `GET /knowledge-points/{knowledge_point_id}/questions`
  - 输出：该知识点关联题目列表。

- [x] `GET /knowledge-points/{knowledge_point_id}/materials`
  - 输出：该知识点关联资料和证据片段。

- [x] `PATCH /knowledge-points/{knowledge_point_id}/mastery`
  - 行为：手动或系统更新掌握状态。

### 目标中心链路调整 TODO

#### QA 调整

当前 QA 主要是：

```text
POST /qa/ask
material_id + question
```

推荐逐步调整为：

```text
target_id + question + optional knowledge_point_id / material_id
```

具体 TODO：

- [x] `qa_records` 增加 `target_id` 字段。
- [x] `qa_records` 保留 `material_id`，但改为主要引用资料语义：表示本次回答主要引用了哪份资料。
- [x] 新增 `qa_knowledge_points`，记录一次问答涉及哪些知识点。
- [x] `POST /qa/ask` 支持 `target_id`。
- [x] `POST /qa/ask` 支持可选 `knowledge_point_id`。
- [x] `POST /qa/ask` 支持可选 `material_id`，用于“只问某份资料”的兼容场景。
- [x] 当传入 `knowledge_point_id` 时，优先收集该知识点关联资料片段作为上下文。
- [x] 当只传入 `target_id` 时，从目标下多个资料中检索相关片段，再回答。
- [x] QA 返回中增加 `knowledge_points` 字段。
- [x] QA 返回中保留 `references`，reference 可指向多个资料片段。

#### 出题调整

当前出题主要是：

```text
POST /questions/generate
material_id + question_types + difficulty + count
```

推荐逐步调整为：

```text
target_id + optional knowledge_point_ids / material_id + question_types + difficulty + count
```

具体 TODO：

- [x] `questions` 增加 `target_id` 字段。
- [x] `questions.material_id` 保留，用于记录主要来源资料，但不再作为唯一生成入口。
- [x] `POST /questions/generate` 支持 `target_id`。
- [x] `POST /questions/generate` 支持可选 `knowledge_point_ids`。
- [x] 当传入 `knowledge_point_ids` 时，题目围绕指定知识点生成。
- [x] 当只传入 `target_id` 时，AI 根据目标下知识点权重和掌握度自动选题。
- [x] 题目入库时必须写入 `question_knowledge_points`。
- [x] 题目返回中保留 `knowledge_points`，供前端展示题目归属。
- [x] 题目生成支持 `extra_requirement`，允许用户补充题目风格、考察重点和场景要求。

#### 错题与掌握度调整

- [x] 自测提交后，根据题目关联知识点更新 `user_knowledge_mastery`。
- [x] 错题生成后写入 `wrong_question_knowledge_points`。
- [x] 知识点错率由 `wrong_count / answered_count` 计算。
- [x] 知识点颜色由错率或掌握状态决定。
- [x] 点击知识点时可查询关联错题。
- [x] 点击知识点时可查询关联题目。
- [x] 点击知识点时可查询关联资料证据。
- [x] 支持手动修正知识点掌握状态。

当前掌握度更新规则：

- 每提交一道已关联知识点的题目，对应知识点 `answered_count + 1`。
- 答错时 `wrong_count + 1`。
- `accuracy = (answered_count - wrong_count) / answered_count`。
- `mastery_score` 暂时等于 `accuracy`，供知识图谱颜色或进度展示。
- `mastery_status` 映射规则：`accuracy < 0.6` 为 `weak`，`0.6 <= accuracy < 0.85` 为 `basic`，`accuracy >= 0.85` 为 `proficient`。
- `next_review_at` 根据掌握状态设置间隔：薄弱 1 天、基本掌握 3 天、熟练 7 天。

#### 复习计划调整

- [ ] 复习计划生成入口优先使用 `target_id`。
- [x] 计划生成时读取该目标下所有知识点掌握度。
- [x] 优先安排 `weak`、高错率、长时间未复习的知识点。
- [x] 复习任务可关联 `knowledge_point_id`。
- [x] 复习任务可同时引用相关错题和资料片段。

### 需要改造的现有模块

- `questions`
  - 生成入口从单一 `material_id` 逐步升级为 `target_id` + 可选知识点。
  - 生成题目时必须返回对应知识点。
  - 题目入库时写入 `question_knowledge_points`。

- `qa`
  - 提问入口从单一 `material_id` 逐步升级为 `target_id` + 可选知识点。
  - 回答上下文从单份资料扩展为目标下相关资料片段。
  - 问答记录写入 `qa_knowledge_points`。

- `tests`
  - 提交测试后按知识点统计正确率。
  - 更新 `user_knowledge_mastery`。

- `wrong_questions`
  - 错题生成时绑定知识点。
  - 支持按知识点筛选。

- `review_plans`
  - 生成复习计划时优先安排薄弱知识点和高错率知识点。

### P0 具体实现拆解

#### 0. 实现边界

第一版 P0 只做“目标级知识点图谱最小闭环”，不一次性重写所有旧接口。

必须完成：

- [x] 可以基于 `target_id` 生成知识点图谱。
- [x] 可以查询某个目标下的知识点图谱。
- [x] 可以基于 `target_id` + 可选 `knowledge_point_ids` 生成题目。
- [x] 题目、自测能写入并更新知识点掌握度。
- [x] 错题写入独立知识点关系表 `wrong_question_knowledge_points`。
- [x] QA 可以接受 `target_id` + 可选 `knowledge_point_id`。

暂时兼容：

- [x] 保留 `material_id` 作为旧接口兼容入口。
- [x] 如果请求只传 `material_id`，后端仍按当前单资料逻辑执行。
- [x] 如果请求传了 `target_id`，优先进入目标级知识点链路。

#### 1. 数据库迁移

新增 Alembic migration，建议命名：

```text
create_knowledge_graph_tables
```

需要新增：

- [ ] `knowledge_points`
- [ ] `material_knowledge_points`
- [ ] `question_knowledge_points`
- [ ] `qa_knowledge_points`
- [x] `wrong_question_knowledge_points`
- [ ] `user_knowledge_mastery`

需要改造：

- [ ] `questions` 增加 `target_id`，允许为空以兼容历史数据。
- [x] `qa_records` 增加 `target_id`，允许为空以兼容历史数据。
- [x] `review_plan_tasks` 如当前没有知识点字段，增加 `knowledge_point_id`，允许为空。

索引建议：

- [ ] `knowledge_points(user_id, target_id)`
- [ ] `knowledge_points(parent_id)`
- [ ] `material_knowledge_points(material_id)`
- [ ] `material_knowledge_points(knowledge_point_id)`
- [ ] `question_knowledge_points(question_id)`
- [ ] `question_knowledge_points(knowledge_point_id)`
- [x] `qa_knowledge_points(qa_record_id)`
- [x] `qa_knowledge_points(knowledge_point_id)`
- [x] `wrong_question_knowledge_points(wrong_question_id)`
- [x] `wrong_question_knowledge_points(knowledge_point_id)`
- [ ] `user_knowledge_mastery(user_id, target_id, knowledge_point_id)` 唯一约束。

#### 2. 模型层

新增文件：

- [ ] `app/models/knowledge_point.py`
- [ ] `app/models/knowledge_relation.py`
- [ ] `app/models/user_knowledge_mastery.py`

需要确认：

- [ ] `app/db/base.py` 引入新模型，保证 Alembic 能感知。
- [ ] `app/models/question.py` 增加 `target_id`。
- [ ] `app/models/qa.py` 增加 `target_id`。
- [x] `app/models/review_plan.py` 的 task 模型增加 `knowledge_point_id`。

枚举建议：

```text
KnowledgePointSource:
  ai_generated
  manual
  material_extracted

MasteryStatus:
  unlearned
  weak
  basic
  proficient
```

#### 3. Schema 层

新增文件：

- [ ] `app/schemas/knowledge_graph.py`
- [ ] `app/schemas/knowledge_point.py`
- [ ] `app/schemas/user_knowledge_mastery.py`

核心 schema：

- [ ] `KnowledgeGraphGenerateRequest`
  - `target_id`
  - `force_regenerate: bool = False`
  - `max_points: int = 20`

- [ ] `KnowledgePointResponse`
  - `id`
  - `parent_id`
  - `name`
  - `description`
  - `importance_weight`
  - `level`
  - `sort_order`
  - `mastery_status`
  - `mastery_score`
  - `accuracy`
  - `wrong_count`
  - `answered_count`

- [ ] `KnowledgeGraphResponse`
  - `target_id`
  - `nodes`
  - `generated_at`

- [ ] `KnowledgePointReference`
  - `id`
  - `name`
  - `importance_weight`

需要改造：

- [ ] `QuestionGenerateRequest` 支持 `target_id`。
- [ ] `QuestionGenerateRequest` 支持 `knowledge_point_ids`。
- [ ] `QaAskRequest` 支持 `target_id`。
- [ ] `QaAskRequest` 支持 `knowledge_point_id`。
- [ ] `QuestionResponse` 返回 `knowledge_points`。
- [ ] `QaRecordResponse` 返回 `knowledge_points`。

#### 4. Repository 层

新增文件：

- [ ] `app/repositories/knowledge_point_repository.py`
- [ ] `app/repositories/knowledge_graph_repository.py`
- [ ] `app/repositories/user_knowledge_mastery_repository.py`

需要提供的方法：

- [ ] `list_by_target(user_id, target_id)`
- [ ] `get_by_id(user_id, knowledge_point_id)`
- [ ] `create_many(points)`
- [ ] `replace_graph_for_target(user_id, target_id, points)`
- [ ] `link_material(material_id, knowledge_point_id, evidence_text, relevance_score)`
- [ ] `link_question(question_id, knowledge_point_id, relevance_score)`
- [ ] `link_qa_record(qa_record_id, knowledge_point_id, relevance_score)`
- [ ] `link_wrong_question(wrong_question_id, knowledge_point_id, wrong_reason)`
- [ ] `get_or_create_mastery(user_id, target_id, knowledge_point_id)`
- [ ] `update_mastery_after_answer(user_id, target_id, knowledge_point_id, is_correct)`
- [ ] `list_wrong_questions_by_knowledge_point(user_id, knowledge_point_id, page, page_size)`
- [ ] `list_questions_by_knowledge_point(user_id, knowledge_point_id, page, page_size)`

#### 5. Service 层

新增文件：

- [ ] `app/services/knowledge_graph_service.py`
- [ ] `app/services/knowledge_mastery_service.py`

`knowledge_graph_service` 负责：

- [ ] 校验目标属于当前用户。
- [ ] 读取目标下所有 `parse_status = parsed` 的资料。
- [ ] 汇总资料文本，控制输入长度。
- [ ] 调用 `ai_service.generate_knowledge_graph()`。
- [ ] 校验 AI 返回 JSON。
- [ ] 写入 `knowledge_points`。
- [ ] 写入 `material_knowledge_points` 证据片段。
- [ ] 初始化 `user_knowledge_mastery`。
- [ ] 返回带掌握度和错率的图谱节点。

`knowledge_mastery_service` 负责：

- [ ] 根据答题结果更新 answered_count。
- [ ] 根据答题结果更新 wrong_count。
- [ ] 计算 accuracy。
- [ ] 根据 `accuracy` 和答题数量计算 `mastery_status`。
- [ ] 更新 `last_practiced_at`。
- [ ] 初步计算 `next_review_at`。

掌握状态第一版规则建议：

```text
answered_count = 0                  -> unlearned
answered_count < 3 或 accuracy < .6 -> weak
accuracy < .85                     -> basic
accuracy >= .85                    -> proficient
```

#### 6. AI Service 层

在 `app/services/ai_service.py` 增加：

- [ ] `generate_knowledge_graph(target_title, subject, materials, max_points)`
- [x] `infer_question_knowledge_points(question, candidate_points)`
- [x] `infer_qa_knowledge_points(question, answer, candidate_points)`

`generate_knowledge_graph()` 输出必须是稳定 JSON，不要让 router 直接解析自然语言。

推荐返回结构：

```json
{
  "points": [
    {
      "name": "进程与线程",
      "description": "进程、线程及其区别与通信方式",
      "importance_weight": 0.92,
      "parent_name": null,
      "level": 1,
      "sort_order": 1,
      "evidence": [
        {
          "material_id": 1,
          "snippet": "进程是资源分配的基本单位..."
        }
      ]
    }
  ]
}
```

AI 失败处理：

- [ ] AI 返回非 JSON 时返回明确错误。
- [ ] AI 返回空知识点时返回明确错误。
- [ ] AI 生成图谱失败不应修改旧图谱，除非 `force_regenerate = true` 且新图谱校验通过。

#### 7. Router 层

新增文件：

- [ ] `app/routers/knowledge_graphs.py`
- [ ] `app/routers/knowledge_points.py`

新增路由：

- [ ] `POST /knowledge-graphs/generate`
- [ ] `GET /knowledge-graphs/{target_id}`
- [ ] `GET /knowledge-points/{knowledge_point_id}/wrong-questions`
- [ ] `GET /knowledge-points/{knowledge_point_id}/questions`
- [ ] `GET /knowledge-points/{knowledge_point_id}/materials`
- [ ] `PATCH /knowledge-points/{knowledge_point_id}/mastery`

需要在 `app/main.py` 注册路由。

#### 8. 改造题目生成

目标：

```text
旧：material_id -> questions
新：target_id + optional knowledge_point_ids -> questions
```

具体任务：

- [ ] `QuestionGenerateRequest.material_id` 改为可选。
- [ ] 新增 `target_id`。
- [ ] 新增 `knowledge_point_ids`。
- [ ] 如果传入 `knowledge_point_ids`，校验这些知识点属于该用户和目标。
- [ ] 如果只传入 `target_id`，从 `user_knowledge_mastery` 中优先选择 weak/basic 知识点。
- [ ] 如果目标还没有知识图谱，返回错误提示前端先生成知识图谱。
- [ ] 生成 prompt 时加入知识点名称、描述、证据片段。
- [ ] 题目保存时写入 `target_id`。
- [ ] 题目保存后写入 `question_knowledge_points`。
- [ ] 返回题目时附带知识点信息。

兼容策略：

- [ ] 如果请求只有 `material_id`，继续走旧逻辑。
- [ ] 旧逻辑生成的题目如果无法匹配知识点，允许 `knowledge_points = []`，但新逻辑必须至少一个知识点。

#### 9. 改造 QA

目标：

```text
旧：material_id + question -> answer
新：target_id + optional knowledge_point_id / material_id + question -> answer
```

具体任务：

- [ ] `QaAskRequest.material_id` 改为可选。
- [ ] 新增 `target_id`。
- [ ] 新增 `knowledge_point_id`。
- [ ] 如果传入 `knowledge_point_id`，校验知识点属于该用户和目标。
- [ ] 如果传入 `knowledge_point_id`，优先读取 `material_knowledge_points.evidence_text` 作为上下文。
- [ ] 如果只传入 `target_id`，从目标下资料中按问题关键词粗检索片段。
- [ ] 回答保存时写入 `target_id`。
- [ ] 回答保存后写入 `qa_knowledge_points`。
- [ ] 返回结果中增加 `knowledge_points`。

兼容策略：

- [ ] 如果请求只有 `material_id`，继续走旧 QA 逻辑。

#### 10. 改造自测与错题

具体任务：

- [ ] 提交测试时读取每道题的 `question_knowledge_points`。
- [ ] 对每个关联知识点调用 `knowledge_mastery_service.update_mastery_after_answer()`。
- [ ] 生成错题时写入 `wrong_question_knowledge_points`。
- [x] 错题列表支持 `knowledge_point_id` 过滤。
- [x] 错题详情返回关联知识点。
- [x] 测试结果返回按知识点聚合的统计摘要。

测试结果新增字段建议：

```json
{
  "knowledge_summary": [
    {
      "knowledge_point_id": 1,
      "name": "进程与线程",
      "answered_count": 3,
      "correct_count": 2,
      "wrong_count": 1,
      "accuracy": 0.67,
      "mastery_status": "basic"
    }
  ]
}
```

#### 11. 改造复习计划

具体任务：

- [ ] 生成复习计划时读取目标下 `user_knowledge_mastery`。
- [ ] 优先选择 `weak`、低 accuracy、高 wrong_count 的知识点。
- [ ] `review_plan_tasks` 写入 `knowledge_point_id`。
- [ ] 任务内容中包含知识点名称、复习建议、关联错题数量。
- [ ] 复习计划返回 task 的 `knowledge_point` 摘要。

#### 12. 测试计划

新增测试文件：

- [ ] `tests/test_knowledge_graphs.py`
- [ ] `tests/test_knowledge_mastery.py`

测试用例：

- [ ] 未登录不能生成知识图谱。
- [ ] 不能为其他用户目标生成知识图谱。
- [ ] 目标下没有 parsed 资料时生成图谱失败。
- [ ] 成功生成知识图谱后能查询节点。
- [ ] 生成题目时传 `knowledge_point_ids` 能写入题目关系。
- [ ] 提交自测后掌握度发生变化。
- [ ] 错题能按知识点查询。
- [ ] QA 传 `knowledge_point_id` 能返回知识点信息。
- [ ] 旧 `material_id` QA 兼容路径仍可用。

#### 13. 推荐开发顺序

第一步：只做图谱生成与查询。

- [ ] migration
- [ ] model
- [ ] schema
- [ ] repository
- [ ] service
- [ ] router
- [ ] `POST /knowledge-graphs/generate`
- [ ] `GET /knowledge-graphs/{target_id}`

第二步：接入题目生成。

- [ ] `questions` 增加 `target_id`
- [ ] `QuestionGenerateRequest` 支持 `target_id` 和 `knowledge_point_ids`
- [ ] 题目保存知识点关系
- [ ] 题目响应返回知识点

第三步：接入自测、错题、掌握度。

- [ ] 自测提交更新掌握度
- [ ] 错题绑定知识点
- [ ] 错题按知识点查询

第四步：接入 QA。

- [ ] `QaAskRequest` 支持 `target_id` 和 `knowledge_point_id`
- [ ] QA 使用知识点证据片段
- [ ] QA 保存知识点关系

第五步：接入复习计划。

- [ ] 复习计划读取掌握度
- [ ] 复习任务绑定知识点

### 验收标准

- [ ] 一个目标可以生成知识点图谱。
- [ ] 每个知识点有重要程度权重。
- [ ] 每道 AI 生成题至少关联一个知识点。
- [ ] QA 可以基于目标提问，也可以基于某个知识点提问。
- [ ] 测试提交后能更新知识点正确率和掌握状态。
- [ ] 错题能按知识点归因。
- [ ] 复习计划能优先引用薄弱知识点。

## P1：AI Tutor 引导式学习模式

### 目标

将部分 QA 从“直接给完整答案”升级为“分步提示 + 答案检查 + 最终解析”。

推荐交互流程：

```text
Hint 1：提示相关概念
Hint 2：提示解题方向
Check my answer：检查学生当前回答
Show full solution：展示完整解析
```

该模块需要记录用户是否真的根据反馈修改行为，而不是只记录 AI 生成内容。

### 推荐新增表

#### `tutor_sessions`

建议字段：

- `id`
- `user_id`
- `target_id`
- `material_id`
- `question_id`
- `knowledge_point_id`
- `session_status`
- `created_at`
- `updated_at`

#### `tutor_messages`

建议字段：

- `id`
- `session_id`
- `role`
- `message_type`
- `content`
- `created_at`

`message_type` 建议值：

```text
student_question
hint
student_answer
answer_check
full_solution
system_feedback
```

#### `feedback_actions`

记录学生收到反馈后的行为。

建议字段：

- `id`
- `session_id`
- `user_id`
- `action_type`
- `before_answer`
- `after_answer`
- `created_at`

`action_type` 建议值：

```text
view_hint
submit_answer
revise_answer
show_solution
mark_mastered
```

### 推荐新增接口

- `POST /tutor/sessions`
  - 创建引导式学习会话。

- `POST /tutor/sessions/{session_id}/hint`
  - 生成下一步提示。

- `POST /tutor/sessions/{session_id}/check`
  - 检查学生答案。

- `POST /tutor/sessions/{session_id}/solution`
  - 展示完整解析。

- `GET /tutor/sessions/{session_id}`
  - 查看完整 tutor 会话。

### 验收标准

- [ ] 可以围绕一个题目或知识点创建 tutor 会话。
- [ ] 至少支持两级 hint。
- [ ] 可以提交答案并调用 AI 检查。
- [ ] 可以记录用户是否查看提示、修改答案、查看完整解析。
- [ ] Tutor 行为能关联到知识点掌握度更新。

## P1：AI 调用日志与 API 计费

### 目标

为 B 侧所有真实 AI 调用增加日志与成本追踪能力，支持后续预算控制、调用排查和用户侧用量展示。

这里不做完整管理员运维中心，只实现 AI 学习闭环所需的调用记录和用量统计。

### 推荐新增或强化表

#### `ai_call_logs`

已实现字段：

- `id`
- `user_id`
- `target_id`
- `material_id`
- `feature`
- `provider`
- `model`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `prompt_cache_hit_tokens`
- `prompt_cache_miss_tokens`
- `reasoning_tokens`
- `estimated_cost`
- `currency`
- `billing_policy_version`
- `status`
- `http_status_code`
- `error_message`
- `latency_ms`
- `prompt_chars`
- `completion_chars`
- `created_at`

当前已接入的 `feature`：

```text
qa
question_generation
wrong_reason_analysis
subjective_score
subjective_scoring
review_plan_generation
knowledge_graph_generation
```

#### `ai_model_pricing`

暂不单独建表。第一版使用 `.env` 中的平台本地价格配置：

```text
AI_BILLING_CURRENCY
AI_BILLING_POLICY_VERSION
AI_PRICE_PROMPT_PER_1K_TOKENS
AI_PRICE_COMPLETION_PER_1K_TOKENS
AI_PRICE_CACHE_HIT_PROMPT_PER_1K_TOKENS
AI_PRICE_CACHE_MISS_PROMPT_PER_1K_TOKENS
AI_PRICE_REASONING_PER_1K_TOKENS
```

#### `user_ai_usage_daily`

暂不单独建表。第一版直接基于 `ai_call_logs` 聚合查询，避免维护冗余统计表。

### 推荐新增接口

- `GET /ai-usage/summary`
  - 学生查看自己的 AI 调用次数、token 用量和本地估算费用。

- `GET /ai-usage/logs`
  - 学生分页查看自己的 AI 调用明细。

### 实现建议

- 所有真实 AI 调用统一经过 `llm_service`。
- `llm_service` 读取 provider 返回的 usage 信息。
- 专门的 `ai_usage_service` 写入日志和统计。
- 对于暂时没有 token usage 的 provider，允许 `prompt_tokens`、`completion_tokens` 为空，但必须记录调用耗时、状态和模型。
- 计费只做估算，不做复杂套餐、余额、扣费逻辑。

### 验收标准

- [x] 主要真实 AI 调用会生成调用日志。
- [x] 可以按用户、模型、功能统计调用次数。
- [x] 可以基于 token 本地估算成本。
- [x] 学生可以查看自己的 AI 使用量。

## P2：导出功能

### 目标

让 B 侧生成的学习成果可以进入真实学习工具链。

优先支持：

- 错题本 Markdown
- 复习计划 Markdown
- 知识点总结 Markdown
- Anki 卡片

后续支持：

- 题目 PDF
- 学习报告 PDF

### 推荐新增接口

- `GET /exports/wrong-questions.md`
- `GET /exports/review-plan/{plan_id}.md`
- `GET /exports/knowledge-summary/{target_id}.md`
- `GET /exports/anki/{target_id}.csv`

### Anki 导出格式

推荐 CSV 字段：

```text
front,back,tags
```

字段说明：

- `front`：问题。
- `back`：答案 + 解析 + 来源。
- `tags`：目标 / 资料 / 知识点。

### 验收标准

- [x] 可以导出某目标下的错题 Markdown。
- [x] 可以导出复习计划 Markdown。
- [x] 可以导出知识提炼 Markdown。
- [x] 可以导出 Anki CSV。
- [x] 导出内容包含知识点标签和资料来源。

## 推荐实现顺序

### 第一阶段：知识点图谱最小闭环

- [ ] 新增 `knowledge_points`。
- [ ] 新增 `question_knowledge_points`。
- [ ] 新增 `user_knowledge_mastery`。
- [ ] 实现 `POST /knowledge-graphs/generate`。
- [ ] 改造题目生成，使题目绑定知识点。
- [ ] 改造测试提交，使掌握度按知识点更新。
- [ ] 实现按知识点查看错题。

### 第二阶段：AI 调用日志与计费

- [x] 统一 AI 调用日志字段。
- [x] 主要真实 AI 功能写入 `ai_call_logs`。
- [x] 新增 token/cost 字段。
- [x] 新增用户 AI 用量统计接口。

### 第三阶段：AI Tutor

- [ ] 新增 tutor session/message/action 表。
- [ ] 实现 hint/check/solution 三类接口。
- [ ] Tutor 行为关联知识点掌握度。

### 第四阶段：导出能力

- [x] 导出错题 Markdown。
- [x] 导出复习计划 Markdown。
- [x] 导出知识提炼 Markdown。
- [x] 导出 Anki CSV。

## 暂不优先事项

- 暂不优先做资料解析、OCR、PDF 结构化解析，这部分交由成员 A。
- 暂不优先做管理员运维中心，这部分交由成员 A。
- 暂不优先做复杂知识图谱可视化算法，前端第一版可以根据后端返回的节点、权重、错率自行布局。
- 暂不优先做复杂计费套餐，只做调用日志和成本估算。
