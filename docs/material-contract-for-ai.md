# AI 模块依赖的资料数据契约

## 1. 文档目的

本文档定义开发成员 B 的 AI 学习闭环模块对开发成员 A 的资料模块的最小依赖。

AI 模块不负责文件上传、文件保存、PDF/TXT 解析或 OCR。AI 模块只消费资料模块已经解析完成后的文本结果。

## 2. 职责边界

开发成员 A 负责：

- 原始文件上传。
- 文件类型和大小校验。
- 文件存储。
- PDF/TXT 文本提取。
- 图片 OCR 或 OCR mock。
- 资料解析状态维护。
- 在 `materials` 表中保存 `parsed_text`。

开发成员 B 负责：

- 校验资料是否可用于 AI。
- 基于 `parsed_text` 生成知识提炼。
- 基于 `parsed_text` 进行 AI 问答。
- 基于 `parsed_text` 生成题目。
- 后续自测评分、错题沉淀和复习计划生成。

## 3. B 模块需要的最小字段

`materials` 表至少需要向 AI 模块提供以下字段：

| 字段 | 类型建议 | 是否必须 | 说明 |
|---|---|---:|---|
| `id` | integer | 是 | 资料 ID |
| `user_id` | integer | 是 | 资料所属用户 |
| `target_id` | integer / nullable | 否 | 所属课程或考试目标 |
| `parse_status` | string / enum | 是 | 资料解析状态 |
| `parsed_text` | text | 是 | 解析后的纯文本内容 |

AI 模块当前查询语义：

```sql
SELECT target_id, parse_status, parsed_text
FROM materials
WHERE id = :material_id AND user_id = :user_id
LIMIT 1
```

## 4. 状态值约定

`parse_status` 建议统一使用以下值：

| 状态 | 含义 | AI 模块处理 |
|---|---|---|
| `uploaded` | 已上传，尚未解析 | 拒绝 AI 处理 |
| `parsing` | 正在解析 | 拒绝 AI 处理 |
| `parsed` | 解析完成 | 允许 AI 处理 |
| `failed` | 解析失败 | 拒绝 AI 处理 |

只有 `parse_status == "parsed"` 时，AI 知识提炼、AI 问答和 AI 出题接口才允许继续执行。

## 5. 当前临时 mock

在 A 的 `materials` 表尚未创建前，B 模块通过 `app/services/material_access_service.py` 提供临时 mock。

当前 mock 数据：

| material_id | user_id | parse_status | 用途 |
|---:|---:|---|---|
| 1 | 1 | `parsed` | 成功场景 |
| 2 | 1 | `parsing` | 未解析完成场景 |
| 3 | 2 | `parsed` | 其他用户资料隔离场景 |

mock fallback 只允许在真实 `materials` 表不存在时启用。其他数据库错误必须暴露出来，避免掩盖集成问题。

## 6. 后续替换计划

当 A 完成资料模块后，B 模块应逐步移除 mock：

1. 确认 `materials` 表字段与本文档一致。
2. 确认 `parse_status` 状态值一致。
3. 使用真实 `materials.parsed_text` 跑通：
   - `POST /knowledge/extract`
   - `POST /qa/ask`
   - `POST /questions/generate`
4. 删除或关闭 `MOCK_MATERIALS` fallback。

## 7. 当前使用方

以下 B 模块接口依赖本契约：

- `POST /knowledge/extract`
- `POST /qa/ask`
- `POST /questions/generate`
