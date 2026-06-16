# AI 智能备考复习平台

这是一个面向学生备考场景的全栈学习平台，后端基于 FastAPI、PostgreSQL、Redis，前端基于 Vite、React、TypeScript。项目已经具备从资料上传、资料解析、知识提炼、AI 问答、AI 出题、自测评分、错题沉淀到复习计划生成的核心闭环，并补齐了学习仪表盘、知识图谱、结构化阅读和导出能力。

## 当前状态

当前代码已完成 `feedback.md` 中 P0/P1 级别的主要修复和前端能力补齐：

- 修复非 Bearer `Authorization` 头提示不准确的问题。
- 修复并发重复注册可能触发数据库异常的问题。
- 新增 `GET /tests/records` 测试记录列表接口。
- 修正前端知识提炼请求，只发送后端要求的 `material_id`。
- 前端新增学习仪表盘、知识图谱页面、结构化资料阅读器和导出按钮。
- 前端支持错题、复习计划、知识点总结、Anki CSV 下载。
- Docker 后端服务、PostgreSQL、Redis 均可正常启动。
- 前端 Vite 开发服务已验证可访问。

本地验证结果：

```text
前端构建：npm run build 通过
后端边界测试：62 passed
后端健康检查：https://localhost/api/health 正常
前端页面：http://127.0.0.1:5173/ 正常
```

## 技术栈

后端：

- Python 3
- FastAPI
- SQLAlchemy async
- Alembic
- PostgreSQL 16
- Redis 7
- Tesseract OCR
- OpenAI-compatible AI API

前端：

- React 18
- TypeScript
- Vite
- lucide-react
- 原生 CSS

基础设施：

- Docker
- Docker Compose
- Caddy HTTPS 入口

## 目录结构

```text
.
├── app/                         # FastAPI 后端应用
│   ├── routers/                 # API 路由
│   ├── repositories/            # 数据访问层
│   ├── schemas/                 # Pydantic Schema
│   ├── models/                  # SQLAlchemy 模型
│   ├── services/                # 业务服务
│   └── dependencies/            # 鉴权等依赖
├── alembic/                     # 数据库迁移
├── frontend/                    # React 前端
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── tests/                       # 后端测试
├── docs/                        # 项目文档和测试资料
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 环境准备

团队成员需要安装：

- Docker Desktop
- Node.js 18 或更高版本
- npm

如果只运行后端和数据库，Docker Desktop 即可。如果要本地开发前端，需要 Node.js 和 npm。

## 配置环境变量

复制环境变量模板：

```bash
copy .env.example .env
```

macOS/Linux 使用：

```bash
cp .env.example .env
```

如需真实 AI 调用，请在 `.env` 中配置：

```text
AI_PROVIDER=openai-compatible
AI_API_KEY=你的 API Key
AI_BASE_URL=https://openrouter.ai/api/v1
AI_MODEL=qwen/qwen3-30b-a3b-instruct-2507
AI_TIMEOUT_SECONDS=60
```

## 启动 Docker HTTPS 环境

在项目根目录执行：

```bash
docker compose up --build -d
```

首次启动或数据库重置后执行迁移：

```bash
docker compose exec api alembic upgrade heads
```

HTTPS 访问入口：

```text
https://localhost
```

Caddy 使用本地内置 CA 签发证书，首次访问时浏览器可能提示证书不受信任。可以先临时继续访问，也可以导出本地 CA 根证书后导入系统或浏览器信任列表：

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-local-root.crt
```

如需在内网主机名下访问，可在 `.env` 中配置：

```text
CADDY_SITE_ADDRESS=https://你的内网主机名
```

然后重新构建并启动：

```bash
docker compose up --build -d
```

API 地址通过 Caddy 统一挂载到 `/api`：

```text
https://localhost/api
https://localhost/api/docs
```

健康检查：

```bash
curl -k https://localhost/api/health
curl -k https://localhost/api/health/db
curl -k https://localhost/api/health/redis
```

Windows PowerShell 也可以使用：

```powershell
Invoke-WebRequest -SkipCertificateCheck -UseBasicParsing https://localhost/api/health
```

默认 Docker 环境不再直接暴露 API、PostgreSQL、Redis 端口到宿主机，外部入口统一走 Caddy 的 80/443。这样登录密码、Bearer token 和资料内容会在浏览器到 Caddy 的链路上通过 HTTPS 加密传输；数据库中仍只保存 bcrypt 哈希后的密码。

## 启动前端

进入前端目录安装依赖：

```bash
cd frontend
npm install
```

启动开发服务：

```bash
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173/
```

本地开发模式下，Vite 会继续把 `/api` 代理到 `localhost:8000`。如果需要使用该开发代理，请叠加开发端口配置启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Docker HTTPS 环境推荐直接访问 `https://localhost`。

构建前端：

```bash
npm run build
```

预览构建结果：

```bash
npm run preview
```

## 一键启动建议

推荐使用 Docker HTTPS 环境：

```bash
docker compose up --build -d
docker compose exec api alembic upgrade heads
```

然后访问：

```text
应用入口：https://localhost
接口文档：https://localhost/api/docs
```

如需前端热更新开发，可开启两个终端：

终端 1：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
docker compose exec api alembic upgrade heads
```

终端 2：

```bash
cd frontend
npm install
npm run dev
```

然后访问：

```text
前端：http://127.0.0.1:5173/
HTTPS 入口：https://localhost
```

## 核心业务流程

```text
注册/登录
-> 创建课程或考试目标
-> 上传 TXT/PDF/图片资料
-> 后台解析资料
-> 结构化阅读
-> 知识提炼
-> 生成知识图谱
-> AI 问答
-> AI 出题
-> 提交自测
-> 自动沉淀错题
-> 生成复习计划
-> 导出错题、计划、知识总结或 Anki 卡片
```

## 前端功能

当前前端包含：

- 登录与注册
- 学习目标管理
- 资料上传与解析状态展示
- 资料详情页
- 结构化章节阅读
- 知识提炼
- 知识图谱页面
- AI 问答
- AI 出题
- 自测提交与结果展示
- 测试记录读取
- 错题本
- 错题掌握状态更新
- 复习计划生成与查看
- 学习仪表盘
- Markdown/CSV 导出

登录后可看到完整学习工作台。未登录时页面停留在登录/注册入口是正常状态。

## 后端主要接口

认证：

```text
POST /auth/register
POST /auth/login
```

学习目标：

```text
GET  /study-targets
POST /study-targets
GET  /study-targets/{target_id}
```

资料：

```text
GET  /materials
POST /materials
GET  /materials/{material_id}
POST /materials/{material_id}/parse
GET  /materials/{material_id}/preview
GET  /materials/{material_id}/sections
GET  /materials/{material_id}/chunks
GET  /materials/{material_id}/structured
```

知识与图谱：

```text
POST /knowledge/extract
GET  /knowledge-graphs/{target_id}
POST /knowledge-graphs/generate
```

AI 问答：

```text
POST /qa/ask
GET  /qa/history
```

题目与自测：

```text
POST /questions/generate
POST /tests/submit
GET  /tests/records
```

错题：

```text
GET   /wrong-questions
PATCH /wrong-questions/{wrong_question_id}/mastery
```

复习计划：

```text
POST /review-plans/generate
GET  /review-plans
```

导出：

```text
GET /exports/wrong-questions.md
GET /exports/review-plan/{plan_id}.md
GET /exports/knowledge-summary/{target_id}.md
GET /exports/anki/{target_id}.csv
```

管理员：

```text
GET  /admin/users
GET  /admin/materials
GET  /admin/tasks
POST /admin/tasks/{task_id}/retry
GET  /admin/logs
```

## 快速接口联调

注册：

```bash
curl -k -X POST https://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "student1", "password": "123456", "display_name": "学生1"}'
```

登录：

```bash
curl -k -X POST https://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "student1", "password": "123456"}'
```

复制响应中的 `data.token.access_token`：

```bash
TOKEN='粘贴 access_token'
```

创建学习目标：

```bash
curl -k -X POST https://localhost/api/study-targets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "软件工程期末复习",
    "subject": "软件工程",
    "target_type": "exam",
    "exam_date": "2026-07-01",
    "review_goal": "掌握重点章节并完成错题复盘"
  }'
```

上传资料：

```bash
curl -k -X POST https://localhost/api/materials \
  -H "Authorization: Bearer $TOKEN" \
  -F "target_id=1" \
  -F "file=@docs/temp/test_materials/test.txt"
```

查看资料：

```bash
curl -k "https://localhost/api/materials?target_id=1" \
  -H "Authorization: Bearer $TOKEN"
```

生成知识图谱：

```bash
curl -k -X POST https://localhost/api/knowledge-graphs/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"target_id": 1}'
```

提交 AI 问答：

```bash
curl -k -X POST https://localhost/api/qa/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"material_id": 1, "question": "这份资料的主要内容是什么？"}'
```

## 资料解析能力

当前支持：

| 文件类型 | 处理方式 |
| --- | --- |
| TXT | 直接读取 UTF-8 文本 |
| 文本型 PDF | 使用 `pypdf` 提取页面文本 |
| 扫描版 PDF | 使用 `pdf2image` 转图片，再通过 Tesseract OCR 识别 |
| 图片 | 使用 Tesseract OCR 识别 |

容器内安装了：

```text
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-chi-sim
poppler-utils
```

检查 OCR 语言包：

```bash
docker compose exec api tesseract --list-langs
```

应至少包含：

```text
chi_sim
eng
osd
```

## 鉴权说明

业务接口需要请求头：

```text
Authorization: Bearer <access_token>
```

常见错误：

```text
未提供认证令牌
认证令牌类型错误
认证令牌已过期
认证令牌无效
```

非 Bearer scheme，例如 `Authorization: Token xxx`，会返回令牌类型错误。

## 测试

安装依赖后可以运行后端测试：

```bash
docker compose exec -T api python -m pytest tests/test_boundary_frontend.py tests/test_auth.py -q
```

当前已验证：

```text
62 passed
```

前端构建：

```bash
cd frontend
npm run build
```

当前已验证构建通过。

## 管理员账号

注册接口默认创建学生账号。需要第一个管理员时，在 `.env` 中配置初始管理员变量后启动后端：

```env
INITIAL_ADMIN_USERNAME=admin1
INITIAL_ADMIN_PASSWORD=请使用强密码
INITIAL_ADMIN_DISPLAY_NAME=管理员1
```

后端启动时如果上述用户名和密码均已配置，并且该用户名尚不存在，就会自动创建
`role = admin` 的账号；如果该用户名已存在，则不会重复创建，也不会覆盖密码。管理员登录后
可访问 `/admin/*`、`/health/db` 和 `/health/redis` 等管理员接口。
首次部署如果先启动服务再执行数据库迁移，迁移完成后重启 API 容器即可触发初始管理员创建。

## 停止服务

停止容器：

```bash
docker compose down
```

停止并清空数据库、Redis 和上传文件卷：

```bash
docker compose down -v
```

谨慎使用 `-v`，它会删除本地 Docker volume 中的数据。

## 分享给团队的注意事项

建议分享源码压缩包时包含：

- `app/`
- `alembic/`
- `frontend/src/`
- `frontend/package.json`
- `frontend/package-lock.json`
- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`
- `.env.example`
- `README.md`
- `tests/`
- `docs/`

不建议包含：

- `.env`
- `frontend/node_modules/`
- `frontend/dist/`
- `.pytest_cache/`
- `__pycache__/`
- `*.tsbuildinfo`
- 本地临时压缩包或运行缓存

## 已知边界

- 真实 AI 能力依赖 `.env` 中的 AI API 配置。
- 复习任务已有 `completed` 字段，但当前重点是计划生成和展示，任务完成状态更新接口仍可后续扩展。
- AI Tutor 分步提示模式尚未实现，需要新增后端表、API 和前端交互。
- 管理员运维中心后端接口已具备基础能力，前端管理面板仍可继续增强。

## 团队协作建议

新成员拿到代码后建议按以下顺序熟悉：

1. 阅读本 README。
2. 启动 Docker 后端并打开 `/docs`。
3. 启动前端并注册一个测试账号。
4. 上传一份 TXT 资料，等待解析完成。
5. 依次体验知识提炼、知识图谱、AI 问答、出题、自测、错题和复习计划。
6. 运行后端测试和前端构建，确认本地环境稳定。
