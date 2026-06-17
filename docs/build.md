# 构建与部署综合文档

本文档覆盖后端、前端、Docker、数据库迁移、AI/OCR 配置和常见问题，适合作为本地开发、课程演示和团队交付的运行手册。

## 1. 环境要求

| 组件 | 要求 |
| --- | --- |
| Docker Desktop | 推荐，用于后端、PostgreSQL、Redis、Worker |
| Node.js | 18 或更高版本 |
| npm | 随 Node.js 安装 |
| Python | Docker 内使用 Python 3.12；本地运行测试时需要 Python 3.12 兼容环境 |

后端容器会安装：

```text
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-chi-sim
poppler-utils
```

这些依赖用于 PDF 转图和 OCR。

## 2. 环境变量

复制模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

关键配置：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | 后端数据库连接 |
| `REDIS_URL` | Redis 连接 |
| `JWT_SECRET_KEY` | JWT 签名密钥，部署时必须修改 |
| `UPLOAD_DIR` | 上传文件目录 |
| `MAX_UPLOAD_SIZE_MB` | 单文件大小上限，默认 50 MB |
| `AI_PROVIDER` | `mock` 或 `openai-compatible` |
| `AI_API_KEY` | 真实 AI Key |
| `AI_BASE_URL` | OpenAI-compatible 服务地址 |
| `AI_MODEL` | AI 模型名 |
| `VISION_ENABLED` | 是否启用视觉解析增强 |
| `VISION_MODEL` | 视觉模型名 |
| `INITIAL_ADMIN_USERNAME` | 初始管理员用户名 |
| `INITIAL_ADMIN_PASSWORD` | 初始管理员密码 |

部署时至少需要修改：

```env
JWT_SECRET_KEY=please-use-a-strong-secret
DEBUG=false
```

## 3. Docker 后端运行

启动完整环境：

```bash
docker compose up --build -d
```

执行数据库迁移：

```bash
docker compose exec -T api alembic upgrade heads
```

访问地址：

```text
API:     http://localhost:8000
Swagger: http://localhost:8000/docs
```

健康检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/redis
```

查看日志：

```bash
docker compose logs -f api
docker compose logs -f worker
```

停止服务：

```bash
docker compose down
```

停止并清空数据库、Redis 和上传文件卷：

```bash
docker compose down -v
```

`-v` 会删除本地 Docker volume，谨慎使用。

## 4. Docker Compose 服务说明

| 服务 | 说明 | 端口 |
| --- | --- | --- |
| `api` | FastAPI 后端 | `8000:8000` |
| `worker` | Celery worker，处理解析和 AI 作业 | 无公开端口 |
| `postgres` | PostgreSQL 16 | `5432:5432` |
| `redis` | Redis 7 | `6379:6379` |

持久化卷：

| Volume | 用途 |
| --- | --- |
| `postgres_data` | PostgreSQL 数据 |
| `redis_data` | Redis 数据 |
| `uploads_data` | 上传文件 |

`worker` 命令监听队列：

```text
parse
ai_material
ai_target
```

## 5. 前端开发运行

安装依赖：

```bash
cd frontend
npm install
```

启动开发服务：

```bash
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

开发代理：

```text
/api/auth/login -> http://localhost:8000/auth/login
```

如果后端不是 `localhost:8000`，可以设置：

```env
VITE_API_BASE_URL=http://your-api-host
```

注意：如果使用绝对后端地址，需要后端或代理正确配置 CORS。

## 6. 前端生产构建

在 `frontend/` 中执行：

```bash
npm run build
```

该命令等价于：

```bash
tsc -b && vite build
```

输出目录：

```text
frontend/dist
```

预览构建结果：

```bash
npm run preview
```

默认访问：

```text
http://127.0.0.1:4173
```

生产部署注意事项：

1. 静态资源可由 Nginx、对象存储或平台静态服务托管。
2. `/api` 需要反向代理到 FastAPI 后端，除非构建时配置了 `VITE_API_BASE_URL`。
3. 文件下载和源文件预览需要保留认证头，因此前端会使用 `fetch -> Blob`，不要直接把文件接口放进未授权 iframe。

## 7. AI 配置

### 7.1 mock 模式

默认模式：

```env
AI_PROVIDER=mock
```

适合本地开发、自动化测试和无网络演示。

### 7.2 OpenAI-compatible 模式

```env
AI_PROVIDER=openai-compatible
AI_API_KEY=your_key
AI_BASE_URL=https://example.com/v1
AI_MODEL=your_model
AI_TIMEOUT_SECONDS=30
```

`AI_BASE_URL` 可以是服务根地址，也可以是完整 chat completions 地址。配置变更后需要重启后端和 worker：

```bash
docker compose up -d --build api worker
```

真实 AI 失败不会自动 fallback 到 mock，目的是暴露真实集成问题。

## 8. OCR 与视觉解析配置

OCR 关键变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OCR_LANGUAGES` | `chi_sim+eng` | Tesseract 语言 |
| `OCR_TIMEOUT_SECONDS` | `30` | 单次 OCR 超时 |
| `PDF_OCR_DPI` | `200` | PDF 转图 DPI |
| `PDF_OCR_MAX_PAGES` | `20` | PDF OCR 最大页数 |
| `PARSED_TEXT_MAX_CHARS` | `20000` | 解析文本保存上限 |

检查容器内 OCR 语言：

```bash
docker compose exec -T api tesseract --list-langs
```

应至少包含：

```text
chi_sim
eng
osd
```

视觉解析增强默认关闭：

```env
VISION_ENABLED=false
```

启用后需要配置视觉模型供应商、Key、模型名和超时。视觉解析结果会被折叠进解析文本和结构化内容，失败时基础 OCR 结果仍可保留。

## 9. 数据库迁移

执行到最新版本：

```bash
docker compose exec -T api alembic upgrade heads
```

查看当前版本：

```bash
docker compose exec -T api alembic current
```

新增数据表或字段时：

1. 修改 `app/models/` 中的 SQLAlchemy 模型。
2. 修改对应 `schemas/`、`repositories/`、`services/`、`routers/`。
3. 新增 Alembic revision。
4. 在测试中导入新模型，避免 SQLite 测试建表遗漏。
5. 补充迁移和接口回归测试。

## 10. 推荐开发流程

终端 1：

```bash
docker compose up --build -d
docker compose exec -T api alembic upgrade heads
docker compose logs -f api worker
```

终端 2：

```bash
cd frontend
npm install
npm run dev
```

终端 3：

```bash
python -m pytest tests/test_boundary_frontend.py tests/test_auth.py tests/test_security.py
```

打开：

```text
前端: http://127.0.0.1:5173
后端: http://localhost:8000/docs
```

## 11. 常见问题

| 问题 | 处理 |
| --- | --- |
| 前端请求 404 | 检查 Vite `/api` 代理和后端端口 |
| 前端请求 401 | 检查登录 token 是否存在，是否使用 Bearer |
| 资料一直 parsing | 查看 worker 是否启动，查看 `docker compose logs worker` |
| OCR 失败 | 检查 Tesseract 语言包、文件是否可读、PDF 是否过长 |
| AI 返回 503 | 检查 `AI_PROVIDER`、Key、Base URL、模型名和网络 |
| Alembic 报多个 head | 使用 `alembic upgrade heads`，不要只升到单个 head |
| 前端构建失败 | 先看 `tsc -b` 类型错误，再看 Vite 打包错误 |
| `.tsbuildinfo` 异常 | 删除 `frontend/*.tsbuildinfo` 后重新构建 |
| 管理员账号未创建 | 确认 `.env` 配置了初始管理员，并在迁移后重启 API |

## 12. 交付包建议

建议包含：

```text
app/
alembic/
frontend/src/
frontend/package.json
frontend/package-lock.json
docker-compose.yml
Dockerfile
requirements.txt
.env.example
pytest.ini
tests/
docs/
README.md
```

不建议包含：

```text
.env
frontend/node_modules/
frontend/dist/
.pytest_cache/
__pycache__/
*.tsbuildinfo
本地数据库卷
本地上传文件卷
真实 API Key
```
