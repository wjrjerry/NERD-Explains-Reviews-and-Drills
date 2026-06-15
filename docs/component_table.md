# 后端组件职责表（成员3）

| 组件 | 职责 | 主要代码锚点 |
|---|---|---|
| 认证服务 (AuthService) | 用户注册、登录、密码哈希、JWT 签发与续期 | `app/services/auth_service.py`, `app/routers/auth.py`, `app/core/security.py` |
| 用户/权限 | 用户信息、角色管理、管理员接口 | `app/models/user.py`, `app/routers/users.py` |
| 课程/目标服务 (StudyTargetService) | 创建/维护课程与考试目标、归属检查 | `app/services/study_target_service.py`, `app/routers/study_targets.py` |
| 资料服务 (MaterialService) | 文件接收、存储、元数据、软删除、预览 | `app/services/material_service.py`, `app/routers/materials.py`, `app/models/material.py` |
| 解析服务 (ParserService) | 文本提取、OCR 调用、解析状态机、parse_error 记录 | `app/services/parser_service.py` |
| AI / LLM 服务 (AiService / LLMService) | 封装对外 AI 调用、重试策略、超时与请求脱敏 | `app/services/ai_service.py`, `app/services/llm_service.py` |
| 问答/出题/测试服务 (QaService/QuestionService/TestService) | 基于资料执行知识提炼、问答、出题、自动评分、错题写入 | `app/services/qa_service.py`, `app/services/question_service.py`, `app/services/test_service.py` |
| 错题与复习计划服务 | 管理错题、生成复习计划与任务 | `app/services/wrong_question_service.py`, `app/services/review_plan_service.py` |
| 数据访问层（Repositories） | 封装增删改查，做归属与事务边界控制 | `app/repositories/*_repository.py` |
| 异步任务/Worker | 运行解析/AI 任务，使用队列/Redis 做任务调度与重试 | `worker/` 或 `app/tasks/*`（项目未实现，规划中） |
| 日志/监控 | 记录 `ai_call_logs`、`admin_logs`、关键事件、导出给 ELK/Promtail | `app/models/ai_call_log.py` (规划), `app/models/admin_log.py` (规划) |


说明：上表中的“规划”表示该组件的模型或持久化表目前在代码库中尚未完全实现，应在后续实现中补齐并创建相应的迁移脚本。