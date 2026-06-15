# 接口规范（摘要）

## 统一响应与分页

统一响应体（所有接口）：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

分页格式（`PageResult`）：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

## 鉴权

- HTTP Header: `Authorization: Bearer <access_token>`
- Token 生成/解析在 `app/core/security.py`。

## 错误码规范（建议）

- 4xxxx: 客户端/业务错误（参数、权限、未找到）
- 5xxxx: 服务端错误

示例映射：
- `40001` 注册失败（用户名已存在）
- `40002` 登录失败（用户名或密码错误）
- `40401` 目标未找到
- `40402` 资料未找到

## 异步任务约定

- 触发异步任务的接口应当立即返回 task id 和目标资源状态，例如：

```json
{
  "code": 0,
  "message": "success",
  "data": { "task_id": "uuid-...", "status": "pending" }
}
```

- 前端可通过 `GET /tasks/{task_id}` 或查询资源（如 `GET /materials/{id}`）来轮询状态。

## 核心接口示例

1) `POST /auth/register`
- 请求：
```json
{"username":"student1","password":"123456","display_name":"学生1"}
```
- 响应（成功）：
```json
{"code":0,"message":"success","data":{"user":{...}}}
```

2) `POST /auth/login`
- 请求：
```json
{"username":"student1","password":"123456"}
```
- 响应（成功）：
```json
{"code":0,"message":"success","data":{"token":{"access_token":"..."},"user":{...}}}
```

3) `POST /materials` 上传（multipart/form-data）
- 请求字段：`target_id`（表单），`file`（上传文件）
- 响应包含 `material` 元数据（含 `parse_status`）

4) `POST /materials/{id}/parse` 触发解析
- 响应返回最新 `material`（含 `parse_status` 和 `parse_error`）

5) `POST /qa/ask`
- 请求：
```json
{"material_id":1, "question":"需求分析的主要目标是什么？"}
```
- 响应：`{code:0,message:'success',data:{answer: '...'}}` 并记录 `qa_records` / `ai_call_logs`。

（更多接口请参考路由目录 `app/routers/` 并将示例补入本文件以供最终报告引用。）
