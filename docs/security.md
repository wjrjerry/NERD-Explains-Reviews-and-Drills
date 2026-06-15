# 可靠性与安全性（成员3 章节）

## 鉴权与权限

- 使用 JWT 作为访问令牌，签发与解析在 `app/core/security.py`。
- `role` 字段区分 `student` / `admin`，管理员路由需额外校验。
- Token 应支持过期、刷新策略（未来可加入 refresh token）。

## 密码与敏感信息管理

- 密码使用 `bcrypt` 哈希（`passlib` 管理）。
- 不在仓库中存储任何 API Key；生产环境使用容器 Secrets 或环境变量管理。

## 用户数据隔离

- 服务层或 Repository 层必需在查询时强制加上 `WHERE user_id = current_user.id`。
- 管理员有审计接口，但应控制返回内容，避免泄露用户敏感数据（如未脱敏的请求体）。

## 文件上传校验

- 允许类型：PDF、TXT、图片（jpg/png）
- 最大单文件大小：建议 20MB（可配置）
- 校验项：MIME 类型、扩展名、最大大小
- 扩展：对 ZIP、可执行或可疑文件拒绝并记录管理员告警

## 解析与 AI 调用失败处理

- 状态机：`pending` -> `running` -> `succeeded` | `failed`
- 失败时写入 `parse_error` 或 `ai_call_logs.error_message`，并增加 `retry_count` 字段（若存在 `ai_tasks`）。
- 自动重试：指数退避、重试上限（例如 3 次），超过后将状态标为 `failed` 并发送管理员告警（邮件/日志）。

## 日志与审计

- 建议记录事件：文件上传、解析开始/结束/失败、AI 调用开始/成功/失败、管理员操作。
- 关键字段：`timestamp`, `actor_id`, `action`, `target_type`, `target_id`, `details`。
- 将日志导出到集中式日志系统（ELK/Promtail）以便监控与告警。

## 速率限制与滥用防护

- 对外部 AI 接口设置每用户限额（例如每天/每分钟配额）并在超额时返回 `429`。
- 对高成本或大输入的请求进行流控并在界面提示。

## 测试与 CI 相关

- 在 CI 环境运行 Alembic 迁移以保证迁移脚本可以执行。
- 对外部 AI 与 OCR 服务使用 Mock，在测试中断言 `ai_call_logs` 的写入行为。

