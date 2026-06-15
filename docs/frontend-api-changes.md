# 前端接口变化说明

本文档说明合并 `origin/feature/auth-materials` 后，当前后端接口和 AI 学习链路相比早期版本的主要变化。

## 1. 总体变化

当前后端已经从“单资料问答/出题”扩展为“目标级学习空间”：

```text
旧链路：
material_id
  -> QA / questions

新链路：
target_id
  -> 多份 materials
  -> 自动解析 parsed_text
  -> 自动知识提炼
  -> 自动知识图谱
  -> 按目标/知识点 QA
  -> 按目标/知识点出题
  -> 自测
  -> 错题归因
  -> 掌握度更新
  -> 复习计划
  -> 导出
```

前端应该优先围绕 `target_id` 组织页面状态。`material_id` 仍然保留，用于资料详情、按单份资料提问、按单份资料生成题目等兼容场景。

## 2. 资料模块变化

### 2.1 上传资料默认自动解析

接口：

```http
POST /materials
```

新增/变化字段：

```text
auto_parse: bool = true
```

前端影响：

- 上传成功后，资料通常不是 `uploaded`，而是很快变成 `parsing`。
- 前端上传后应轮询 `GET /materials/{id}` 或刷新资料列表。
- 不应假设上传后必须再手动调用 `POST /materials/{id}/parse`。

推荐页面行为：

```text
上传成功
  -> 展示资料卡片
  -> parse_status = parsing
  -> 显示解析中
  -> 每 1~3 秒轮询资料详情或列表
  -> parsed 后启用 AI 功能
  -> failed 后展示 parse_error 和重试入口
```

如前端希望用户手动控制解析，可上传时传：

```text
auto_parse=false
```

### 2.2 手动解析改为后台任务

接口：

```http
POST /materials/{material_id}/parse
```

变化：

- 旧理解：请求返回时解析已经完成。
- 当前实现：请求只创建后台解析任务并立即返回。

前端影响：

- 调用后不要立即进入 AI 页面。
- 应根据 `parse_status` 轮询。

### 2.3 PDF / 图片解析能力变化

当前解析能力：

| 类型 | 当前处理 |
|---|---|
| TXT | 直接读取文本 |
| 文本型 PDF | 使用 pypdf 提取文本 |
| 扫描版 PDF | 转图片后 OCR |
| 图片 | Tesseract OCR |

前端影响：

- PDF/图片不再一定是“暂不支持”。
- 但 OCR 可能失败，仍要展示 `parse_error`。
- PDF OCR 最多处理前 20 页，过长资料前端可提示用户拆分。

### 2.4 新增解析质量提示和结构化内容

资料响应新增：

```text
parse_warning: string | null
```

含义：

- `parse_error` 表示解析失败，通常对应 `parse_status=failed`。
- `parse_warning` 表示解析成功或部分成功，但质量可能不稳定。
- 例如 OCR 文本过短、疑似乱码、碎片行较多、PDF 部分页 OCR 失败、解析文本被截断。

前端影响：

- 当 `parse_status=parsed` 且 `parse_warning != null` 时，AI 功能可以启用，但应提示用户“解析质量可能影响回答/出题效果”。
- 资料卡片或资料详情页建议展示 warning 图标或黄色提示。
- 不要把 `parse_warning` 当作失败处理。

推荐页面行为：

```text
parse_status=parsed, parse_warning=null
  -> 正常展示“可学习”

parse_status=parsed, parse_warning!=null
  -> 展示“可学习，但建议校对”
  -> 允许 QA / 出题 / 图谱

parse_status=failed
  -> 展示 parse_error
  -> 提供重新解析入口
```

### 2.5 新增结构化解析结果

资料解析成功后，后端不只保存 `parsed_text`，还会生成 MVP 版结构化结果：

```text
material_sections
material_chunks
material_figures
material_tables
material_formulas
```

新增接口：

```http
GET /materials/{material_id}/sections
GET /materials/{material_id}/chunks
GET /materials/{material_id}/chunks?section_id=1
GET /materials/{material_id}/figures
GET /materials/{material_id}/tables
GET /materials/{material_id}/formulas
GET /materials/{material_id}/structured
GET /study-targets/{target_id}/chunks?limit=200
```

前端影响：

- 资料详情页可以展示章节目录和文本块。
- 复杂 slides、几何题、流程图资料可以展示图片说明、表格和公式。
- 目标学习页可以基于目标级 chunks 展示结构化资料片段。
- AI 问答/出题仍由后端读取资料内容，前端不需要把 chunks 再传回 AI 接口。
- 知识提炼、QA、出题、知识图谱仍可继续使用原有接口；chunks 主要是给更细粒度页面和 B 模块能力使用。
- 如果 `parse_warning` 不为空，建议在资料卡片或详情页显示弱提示。
- 前端仍不应该依赖完整 `parsed_text`，因为列表和详情接口不会返回它。

`chunk_type` 当前可选：

```text
text
definition
formula
example
key_sentence
```

### 2.6 多模态视觉解析状态

几何题、复杂 slides、公式图形等多模态视觉解析已经作为可选增强能力接入。

当前接口层面不需要为多模态视觉解析新增独立页面流程：

- 继续通过资料上传和解析状态流转。
- 继续使用 `parse_status`、`parse_error`、`parse_warning`。
- 视觉解析结果会合成为兼容版 `parsed_text`，并同步进入 `material_chunks`。
- 图片说明、表格和公式可通过 `figures/tables/formulas/structured` 接口读取。
- 如果视觉解析失败，后端仍保留基础 OCR 结果，不会让 OCR 成功资料整体失败。

## 3. 自动知识提炼与知识图谱变化

资料解析成功后，后端会自动触发：

```text
1. 结构化解析 material_sections / material_chunks
2. 资料级知识提炼
3. 目标级知识提炼
4. 目标级知识图谱刷新
```

相关表/语义：

```text
knowledge_extractions(scope=material)
knowledge_extractions(scope=target)
knowledge_points
material_knowledge_points
user_knowledge_mastery
```

前端影响：

- 上传并解析资料后，不一定需要用户手动点“生成知识图谱”。
- 前端可以在资料 `parsed` 后调用：

```http
GET /knowledge-graphs/{target_id}
```

如果返回节点为空，或者用户想强制刷新，再调用：

```http
POST /knowledge-graphs/generate
```

或：

```http
POST /knowledge/extract
```

目标级知识提炼接口会同时刷新知识图谱。

## 4. 知识提炼接口变化

知识提炼现在默认由后端自动触发。

资料解析成功后，后端会自动执行：

```text
资料级知识提炼
  -> 目标级知识提炼
  -> 目标级知识图谱刷新
```

因此前端在普通上传资料流程中，不需要主动调用：

```http
POST /knowledge/extract
```

该接口仍然保留，作为手动刷新或失败重试入口。

资料级手动刷新：

```json
{
  "material_id": 1
}
```

目标级手动刷新：

```json
{
  "target_id": 1,
  "force_regenerate": true
}
```

限制：

- `material_id` 和 `target_id` 必须二选一。
- 不能同时传。

前端影响：

- 上传资料后只需要轮询资料 `parse_status`。
- `parse_status=parsed` 后刷新知识图谱和知识提炼展示即可。
- 资料详情页可以提供“重新提炼本资料”。
- 目标知识页可以提供“刷新目标知识提炼/图谱”。

## 5. QA 问答变化

接口：

```http
POST /qa/ask
```

旧模式仍可用：

```json
{
  "material_id": 1,
  "question": "需求分析是什么？"
}
```

新增目标级模式：

```json
{
  "target_id": 1,
  "question": "需求分析和系统设计有什么区别？"
}
```

新增知识点聚焦模式：

```json
{
  "target_id": 1,
  "knowledge_point_id": 3,
  "question": "这个知识点有哪些易错点？"
}
```

响应新增/强化：

```json
{
  "target_id": 1,
  "knowledge_points": [
    {
      "id": 3,
      "name": "需求分析",
      "importance_weight": 0.9
    }
  ]
}
```

前端影响：

- QA 面板建议支持目标级提问。
- 在知识点详情页，可以带 `knowledge_point_id` 发起聚焦提问。
- `material_id` 在目标级回答中表示主要引用资料，不再代表唯一上下文。

## 6. 出题接口变化

接口：

```http
POST /questions/generate
```

旧单资料模式仍可用：

```json
{
  "material_id": 1,
  "question_types": ["single_choice"],
  "difficulty": "medium",
  "count": 3
}
```

新增目标/知识点模式：

```json
{
  "target_id": 1,
  "knowledge_point_ids": [3, 4],
  "question_types": ["single_choice", "multiple_choice", "true_false", "subjective"],
  "difficulty": "medium",
  "count": 5,
  "extra_requirement": "偏期末考试风格"
}
```

前端影响：

- 出题页建议优先使用 `target_id`。
- 知识点图谱页点击节点后，可把节点 ID 放入 `knowledge_point_ids`。
- 用户自定义出题要求填入 `extra_requirement`。
- 返回题目会带 `knowledge_point_ids`，自测结果可按知识点归因。

## 7. 自测与错题变化

自测提交：

```http
POST /tests/submit
```

响应新增知识点维度统计：

```json
{
  "knowledge_point_summary": [
    {
      "knowledge_point_id": 3,
      "total_count": 2,
      "correct_count": 1,
      "wrong_count": 1,
      "accuracy": 0.5,
      "average_score": 0.5
    }
  ]
}
```

错题列表支持知识点筛选：

```http
GET /wrong-questions?knowledge_point_id=3
```

前端影响：

- 测试结果页可以显示“按知识点表现”。
- 知识点详情页可以直接展示相关错题。
- 错题卡片包含 `knowledge_point_ids`。

## 8. 复习计划变化

接口：

```http
POST /review-plans/generate
```

当前复习计划会优先参考：

- 知识点掌握度。
- 错题数量。
- 正确率。
- 资料关联证据。

任务字段新增：

```json
{
  "knowledge_point_id": 3,
  "material_id": 1,
  "wrong_question_id": 2
}
```

前端影响：

- 复习计划任务可跳转到知识点、资料或错题。
- 计划页不再只是文本列表，可以成为学习导航入口。

## 9. 新增 AI 用量接口

用户可以查看自己的 AI token 消耗。

```http
GET /ai-usage/summary
GET /ai-usage/logs
```

前端影响：

- 可新增“AI 用量”页面或用户菜单入口。
- `estimated_cost` 是平台本地估算，不等同供应商官方账单。

## 10. 新增导出接口

```http
GET /exports/wrong-questions.md
GET /exports/review-plan/{plan_id}.md
GET /exports/knowledge-summary/{target_id}.md
GET /exports/anki/{target_id}.csv
```

前端影响：

- 这些接口返回文件，不是统一 JSON。
- 前端可直接用浏览器下载或 `fetch -> Blob`。

## 11. 新增管理员接口

管理员接口前缀：

```text
/admin
```

新增能力：

- 用户列表。
- 全部资料列表。
- 解析任务列表。
- 失败任务重试。
- 管理员操作日志。

前端影响：

- 普通学生端可以忽略。
- 如果有管理员端，需要根据 `user.role === "admin"` 显示入口。

## 12. 当前推荐页面流程

### 学生上传资料后的流程

```text
POST /materials(auto_parse=true)
  -> 返回 material.parse_status=parsing
  -> 前端轮询 GET /materials/{id}
  -> parsed:
       如有 parse_warning，展示解析质量提示
       可选调用 GET /materials/{id}/sections 或 /structured 展示章节目录
       启用 QA / 出题 / 图谱 / 提炼
       可选调用 GET /study-targets/{target_id}/chunks 获取目标级结构化上下文
       刷新 GET /knowledge-graphs/{target_id}
  -> failed:
       展示 parse_error
       提供 POST /materials/{id}/parse 重试
```

### 知识图谱页流程

```text
进入目标详情页
  -> GET /knowledge-graphs/{target_id}
  -> 如果 nodes 有内容：渲染图谱
  -> 如果 nodes 为空：显示“暂无知识图谱”
  -> 用户可点击刷新：
       POST /knowledge/extract { target_id, force_regenerate: true }
       或 POST /knowledge-graphs/generate
```

### 知识点详情页流程

```text
点击图谱节点
  -> GET /knowledge-points/{id}/materials
  -> GET /knowledge-points/{id}/questions
  -> GET /knowledge-points/{id}/wrong-questions
  -> 可发起 POST /qa/ask，携带 target_id + knowledge_point_id
```

### 练习流程

```text
POST /questions/generate
  -> 展示题目
  -> POST /tests/submit
  -> 展示总分、逐题反馈、knowledge_point_summary
  -> GET /wrong-questions 刷新错题本
  -> GET /knowledge-graphs/{target_id} 刷新掌握度颜色
```

## 13. 前端需要特别注意的兼容点

1. `POST /materials` 上传后默认自动解析，不要重复无脑调用 parse。
2. 解析是后台任务，不要把 parse 接口当作同步接口。
3. AI 功能必须等资料 `parse_status=parsed`。
4. `parse_warning` 是质量提示，不是失败；资料仍可进入 AI 功能。
5. 目标级 QA/出题推荐使用 `target_id`，单资料模式只是兼容和精确场景。
6. 结构化资料接口已经可用，资料详情页可选展示 sections/chunks。
7. 知识图谱可能是自动生成的，也可能需要用户手动刷新。
8. 导出接口不是 JSON。
9. 管理员接口需要 admin 角色。
10. PDF/图片解析依赖 OCR 环境，失败时必须展示 `parse_error`，低质量时展示 `parse_warning`。
