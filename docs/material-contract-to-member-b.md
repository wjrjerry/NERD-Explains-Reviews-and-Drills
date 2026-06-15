# 给成员 B 的资料模块对接说明

## 1. 当前资料链路状态

A 模块已经完成真实资料链路：

- 用户登录后创建课程/考试目标。
- 用户通过 `POST /materials` 上传资料。
- 上传成功后默认创建后台解析任务，资料状态先变为 `parsing`。
- 后台解析完成后，资料状态变为 `parsed` 或 `failed`。
- 解析文本统一保存在 `materials.parsed_text`。
- 解析失败原因保存在 `materials.parse_error`。

因此，B 模块不能假设“上传接口返回后资料马上可用于 AI”。如果资料仍是 `parsing`，这是正常状态。

## 2. B 模块需要依赖的字段

AI 相关接口读取资料时，建议至少使用这些字段：

| 字段 | 说明 |
|---|---|
| `materials.id` | 资料 ID，即 AI 接口里的 `material_id` |
| `materials.user_id` | 资料所属用户 ID，用于用户隔离 |
| `materials.target_id` | 资料所属课程/考试目标 ID |
| `materials.parse_status` | 资料解析状态 |
| `materials.parsed_text` | 解析后的纯文本 |
| `materials.parse_error` | 解析失败原因 |

## 3. 查询规则

B 模块查询资料时必须带上当前登录用户 ID：

```sql
SELECT id, user_id, target_id, parse_status, parsed_text, parse_error
FROM materials
WHERE id = :material_id
  AND user_id = :current_user_id
  AND is_deleted = false
LIMIT 1;
```

不要只按 `material_id` 查询，否则会出现用户越权读取他人资料的问题。

## 4. 状态处理规则

`parse_status` 当前有四种状态：

| 状态 | 含义 | B 模块处理方式 |
|---|---|---|
| `uploaded` | 已上传，尚未解析 | 拒绝 AI 处理，提示资料尚未解析 |
| `parsing` | 正在后台解析 | 拒绝 AI 处理，提示稍后再试 |
| `parsed` | 解析完成 | 允许调用知识提炼、问答、出题 |
| `failed` | 解析失败 | 拒绝 AI 处理，展示或转述 `parse_error` |

B 模块只有在满足下面两个条件时才能继续调用 AI：

```text
parse_status == "parsed"
parsed_text 非空
```

建议伪代码：

```python
material = get_material_by_id_and_user_id(material_id, current_user.id)

if material is None:
    raise ValueError("资料不存在")

if material.parse_status == "parsing":
    raise ValueError("资料正在解析中，请稍后再试")

if material.parse_status == "failed":
    raise ValueError(f"资料解析失败：{material.parse_error or '未知错误'}")

if material.parse_status != "parsed":
    raise ValueError("资料尚未解析完成")

if not material.parsed_text:
    raise ValueError("资料解析文本为空")

parsed_text = material.parsed_text
target_id = material.target_id
```

## 5. 当前支持的文件解析能力

| 文件类型 | 当前实现 |
|---|---|
| TXT | 直接读取 UTF-8 文本 |
| 文本型 PDF | 使用 `pypdf` 提取页面文本 |
| 扫描版 PDF | 使用 `pdf2image` 转图片，再用 Tesseract OCR |
| 图片 | 使用 Tesseract OCR，支持 `chi_sim+eng` |

## 6. 解析任务

A 模块新增了 `parse_tasks` 表，用于追踪后台解析任务。

任务状态：

```text
pending
running
succeeded
failed
```

管理员可以通过：

```text
GET /admin/tasks
GET /admin/tasks?status=failed
POST /admin/tasks/{task_id}/retry
```

注意：`POST /admin/tasks/{task_id}/retry` 中的 ID 是 `parse_tasks.id`，不是 `materials.id`。

## 7. 建议联调用例

请 B 模块至少用三类资料测试：

1. `parsed` 状态资料：
   - `POST /knowledge/extract`
   - `POST /qa/ask`
   - `POST /questions/generate`
   - 预期：正常返回 AI 结果。

2. `parsing` 状态资料：
   - 上传资料后立刻调用 AI 接口。
   - 预期：返回“资料正在解析中，请稍后再试”之类提示。

3. `failed` 状态资料：
   - 使用解析失败资料调用 AI 接口。
   - 预期：返回“资料解析失败”，不要调用 AI。

## 8. 对前端和 B 模块的共同提醒

资料上传接口现在是异步解析：

```text
POST /materials -> 返回 parsing -> 后台解析 -> parsed 或 failed
```

因此前端或 B 模块需要通过资料详情 / 列表接口轮询状态，不能依赖上传响应马上进入 AI 流程。
