# 前端综合文档

本文档面向前端开发、联调和验收，覆盖当前 React 单页应用的页面功能、接口调用约定、状态流转和注意事项。

## 1. 前端概览

前端位于 `frontend/`，技术栈如下：

| 类型 | 当前实现 |
| --- | --- |
| 构建工具 | Vite 6 |
| UI 框架 | React 18 + TypeScript |
| 样式 | 原生 CSS，入口 `frontend/src/styles.css` |
| 图标 | `lucide-react` |
| Markdown 渲染 | `react-markdown` + `remark-gfm` |
| API 封装 | `frontend/src/api.ts` |
| 主应用入口 | `frontend/src/App.tsx` |
| 类型定义 | `frontend/src/types.ts` |

前端默认通过 `/api` 访问后端。开发环境下 Vite 会把 `/api/*` 代理到 `http://localhost:8000/*`，生产部署时需要由网关或静态服务提供同样的反向代理，或通过 `VITE_API_BASE_URL` 指定后端地址。

## 2. 页面与功能模块

学生端主导航包括：

| 页面 | 主要能力 | 核心接口 |
| --- | --- | --- |
| 学习仪表盘 | 展示目标、资料数量、测试表现、近期复习任务 | `/study-targets`, `/materials`, `/review-plans` |
| 目标管理 | 创建、查看、更新、删除课程或考试目标 | `/study-targets` |
| 资料库 | 上传 TXT/PDF/图片资料，查看解析状态，删除资料 | `/materials`, `/materials/{id}/parse` |
| 资料详情 | 源文件预览、解析文本预览、结构化章节/chunks/图表公式查看 | `/materials/{id}/file`, `/preview`, `/structured` |
| 知识图谱 | 查看目标级图谱、资料级知识提炼、节点证据和掌握度 | `/knowledge-graphs`, `/knowledge-points`, `/knowledge-jobs` |
| AI 问答 | 按目标、资料或知识点提问，查看 QA 历史 | `/qa/ask`, `/qa/history` |
| AI 出题 | 按资料、目标、知识点生成题目，支持提示、解析和追问 | `/questions/generate`, `/questions/{id}/hints/{level}`, `/solution`, `/explain` |
| 错题本 | 条件筛选错题、更新掌握状态、进入错题复做队列 | `/wrong-questions`, `/review-queue`, `/redo` |
| 复习计划 | 生成复习计划，查看任务，标记任务完成状态 | `/review-plans/generate`, `/review-plans/tasks/{id}` |
| AI 用量 | 查看 AI 调用次数、token、估算费用和调用日志 | `/ai-usage/summary`, `/ai-usage/logs` |

管理员端仅在 `user.role === "admin"` 时展示，包含：

| 页面 | 主要能力 | 核心接口 |
| --- | --- | --- |
| 后台总览 | 用户数、资料解析状态、任务状态、AI 调用概览 | `/admin/summary` |
| 用户管理 | 用户列表、启用/停用账号 | `/admin/users`, `/admin/users/{id}/status` |
| 资料管理 | 全局资料列表，按解析状态查看 | `/admin/materials` |
| 解析任务 | 查看解析任务，重试失败任务 | `/admin/tasks`, `/admin/tasks/{id}/retry` |
| 操作日志 | 查看管理员操作记录 | `/admin/logs` |
| 系统健康 | 检查 API、数据库、Redis 状态 | `/health`, `/health/db`, `/health/redis` |

## 3. 接口调用约定

### 3.1 API 基础路径

`frontend/src/api.ts` 中的默认配置为：

```ts
const DEFAULT_API_BASE = "/api";
const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);
```

开发环境代理配置在 `frontend/vite.config.ts`：

```ts
server: {
  port: 5173,
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, "")
    }
  }
}
```

### 3.2 认证与 token

登录成功后，前端把 `data.token.access_token` 写入 `localStorage`，键名为 `ai_review_token`。后续业务请求统一携带：

```http
Authorization: Bearer <access_token>
```

退出登录时调用 `clearToken()` 清除本地 token，并回到登录/注册页。

### 3.3 JSON 响应

后端大多数接口返回统一包装：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页数据位于 `data`：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

文件类接口例外：

| 接口 | 返回类型 | 前端处理 |
| --- | --- | --- |
| `GET /materials/{id}/file` | 源文件流 | `fetch -> Blob -> URL.createObjectURL` |
| `GET /exports/*.md` | Markdown 文件 | `fetch -> Blob -> a.download` |
| `GET /exports/anki/{target_id}.csv` | CSV 文件 | `fetch -> Blob -> a.download` |

## 4. 关键交互流程

### 4.1 登录和初始化

1. 页面启动时读取本地 token。
2. 有 token 时调用 `GET /users/me`。
3. 成功后加载学生端基础数据：目标、资料、QA 历史、错题、复习计划、AI 用量等。
4. 若用户是管理员，再加载后台总览、用户、资料、任务、日志和健康状态。

### 4.2 资料上传和解析轮询

资料上传调用：

```http
POST /materials
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 说明 |
| --- | --- |
| `target_id` | 资料所属学习目标 ID |
| `auto_parse` | 是否上传后自动解析，前端默认 `true` |
| `file` | TXT/PDF/PNG/JPG/JPEG/WEBP |

状态流转：

```text
uploaded -> parsing -> parsed
uploaded -> parsing -> failed
```

前端轮询参数：

| 类型 | 当前值 |
| --- | --- |
| 解析轮询间隔 | `2500ms` |
| 解析轮询最大次数 | `30` |
| 知识任务轮询间隔 | `2000ms` |
| 知识任务最大次数 | `45` |

页面行为建议：

| 状态 | 前端行为 |
| --- | --- |
| `uploaded` | 展示“等待解析”，允许手动触发解析 |
| `parsing` | 展示“解析中”，禁用 AI 问答、出题和图谱刷新入口 |
| `parsed` | 开放结构化阅读、知识提炼、问答、出题、复习等能力 |
| `failed` | 展示 `parse_error`，提供重新解析入口 |

`parse_warning` 表示资料已解析但质量可能较低，例如 OCR 文本过短、部分页失败或文本被截断。此时 AI 功能仍可使用，但应给用户弱提示。

### 4.3 结构化阅读

资料详情页可读取：

```http
GET /materials/{id}/preview
GET /materials/{id}/file
GET /materials/{id}/structured
GET /materials/{id}/sections
GET /materials/{id}/chunks
GET /materials/{id}/figures
GET /materials/{id}/tables
GET /materials/{id}/formulas
```

`/file` 成功时不返回 JSON。由于浏览器的 `iframe` 和 `img` 不能直接携带 `Authorization`，前端必须先用 `fetch` 获取 Blob，再创建本地 URL。切换资料或离开页面时需要 `URL.revokeObjectURL(url)` 释放资源。

### 4.4 知识图谱和知识作业

知识相关能力分两类：

| 类型 | 接口 | 用途 |
| --- | --- | --- |
| 同步提炼 | `POST /knowledge/extract` | 直接得到资料级或目标级知识摘要 |
| 后台作业 | `/knowledge-jobs/*` | 资料提炼、目标提炼、图谱刷新，适合前端轮询 |

图谱刷新推荐使用：

```http
POST /knowledge-jobs/graph-refresh
GET /knowledge-jobs/{job_id}
GET /knowledge-graphs/{target_id}
```

前端需要注意：目标级图谱依赖已解析资料。若图谱为空，可以提示用户先上传并解析资料，或触发刷新作业。

### 4.5 AI 问答、出题和自测

AI 问答支持三种上下文：

| 模式 | 请求字段 |
| --- | --- |
| 资料级 | `material_id + question` |
| 目标级 | `target_id + question` |
| 知识点聚焦 | `target_id + knowledge_point_id/knowledge_point_ids + question` |

AI 出题支持题型：

```text
single_choice
multiple_choice
true_false
subjective
```

自测提交：

```http
POST /tests/submit
```

客观题使用 `answer`，主观题使用 `answer_text`。提交后后端会评分、保存测试记录、生成错题、更新知识点掌握度。

前端 `api.ts` 中目前保留了 `listTestRecords()` 对 `GET /tests/records` 的调用，但当前后端路由未暴露该接口。展示自测记录时应先确认后端补齐接口，或在前端降级为仅展示本轮提交结果。

### 4.6 错题复做和复习计划

错题本支持：

```http
GET /wrong-questions
GET /wrong-questions/review-queue
POST /wrong-questions/{id}/redo
PATCH /wrong-questions/{id}/mastery
```

掌握状态：

```text
unmastered
reviewing
mastered
```

复习计划支持：

```http
POST /review-plans/generate
GET /review-plans
PATCH /review-plans/tasks/{task_id}
```

计划任务可关联知识点、资料和错题。前端可把计划页作为复习入口，而不只是文本列表。

## 5. 用户体验与错误处理

前端统一从接口错误体中读取 `detail` 或 `message`，展示为页面通知。重点处理：

| 场景 | 建议提示 |
| --- | --- |
| 未登录或 token 失效 | 提示重新登录 |
| 资料未解析 | 提示等待解析完成 |
| 解析失败 | 展示 `parse_error` 和重试入口 |
| 解析质量警告 | 弱提示，允许继续使用 AI |
| AI 服务不可用 | 提示模型配置、网络或超时问题 |
| 管理员接口 403 | 隐藏入口或提示权限不足 |

## 6. 前端维护注意事项

1. 新增页面时优先复用 `api.ts` 的统一请求封装，保持 token、错误读取和 JSON envelope 处理一致。
2. 不要把完整 `parsed_text` 作为页面全局状态长期保存，长文本只在预览区域分页展示。
3. 资料源文件 Blob URL 必须在不再使用时释放。
4. AI 功能入口必须检查资料或目标是否具备可用上下文，避免对未解析资料发起请求。
5. 管理员端入口只根据当前用户角色展示，不要让普通学生看到后台导航。
6. 前端构建前需保证后端新增接口已同步到 `types.ts` 和 `api.ts`。
