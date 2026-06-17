# 数据库并发测试运行说明

本文档说明如何运行 `DB-C01` 到 `DB-C14` 的后端数据库并发测试，以及如何阅读测试输出。

## 覆盖范围

新增测试文件：

| 文件 | 覆盖用例 |
|---|---|
| `tests/test_db_concurrency_c01_c05.py` | DB-C01 到 DB-C05：注册、登录、管理员用户状态、学习目标创建/更新/删除 |
| `tests/test_db_concurrency_c06_c11.py` | DB-C06 到 DB-C11：材料上传、重复解析、删除读竞争、解析任务状态机、结构化结果替换/读写竞争 |
| `tests/test_db_concurrency_c12_c14.py` | DB-C12 到 DB-C14：知识任务 dedupe、running/rerun、知识图谱并发生成 |
| `tests/concurrency_helpers.py` | 并发执行、统计输出、通用 API 测试 helper |

对应设计表见：

`tests/database_concurrency_performance_test_plan.md`

<!-- ## 安装依赖

```bash
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
``` -->

## 快速运行

有后端环境可直接 docker compose 运行

```bash
docker compose exec api python -m pytest tests/test_db_concurrency_c18_c24.py -s
```

或者安装依赖运行

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -s `
  tests\test_db_concurrency_c01_c05.py `
  tests\test_db_concurrency_c06_c11.py `
  tests\test_db_concurrency_c12_c14.py
```

Linux/macOS：

```bash
./.venv/bin/python -m pytest -q -s \
  tests/test_db_concurrency_c01_c05.py \
  tests/test_db_concurrency_c06_c11.py \
  tests/test_db_concurrency_c12_c14.py
```

<!-- 必须加 `-s`，否则 pytest 会捕获 stdout，看不到每个并发用例的统计信息。 -->



## 输出格式

每个用例都会打印类似信息：

```text
[DB-CONCURRENCY] case=DB-C12
  module=knowledge job dedupe
  code_paths=app/routers/knowledge_jobs.py, app/services/knowledge_job_service.py, ...
  concurrent_requests=10
  success=10
  failed=0
  elapsed_seconds=0.2670
  status_counts={'200': 10}
  api_code_counts={'0': 10}
  notes=Concurrent graph-refresh enqueue requests should collapse onto one dedupe_key row.
```

字段含义：

| 字段 | 含义 |
|---|---|
| `case` | 测试计划中的用例编号 |
| `module` | 被测功能模块 |
| `code_paths` | 该用例对应的核心后端代码路径 |
| `concurrent_requests` | 本次并发请求/操作数量 |
| `success` / `failed` | 符合该用例预期的成功/失败数量 |
| `elapsed_seconds` | 并发操作总耗时 |
| `status_counts` | HTTP 状态码或直接仓储操作结果分布 |
| `api_code_counts` | 业务响应 `code` 分布；仓储级测试会显示 `None` |

## 调整并发规模

每个用例都有独立环境变量，可按需放大：

```powershell
$env:DB_C01_CONCURRENCY=50
$env:DB_C06_CONCURRENCY=30
$env:DB_C14_CONCURRENCY=10
.\.venv\Scripts\python.exe -m pytest -q -s tests\test_db_concurrency_c12_c14.py
```

常用变量：

| 变量 | 默认值 |
|---|---:|
| `DB_C01_CONCURRENCY` | 12 |
| `DB_C02_CONCURRENCY` | 16 |
| `DB_C03_CONCURRENCY` | 10 |
| `DB_C04_CONCURRENCY` | 14 |
| `DB_C05_CONCURRENCY` | 12 |
| `DB_C06_CONCURRENCY` | 8 |
| `DB_C07_CONCURRENCY` | 8 |
| `DB_C08_CONCURRENCY` | 10 |
| `DB_C09_CONCURRENCY` | 12 |
| `DB_C10_CONCURRENCY` | 5 |
| `DB_C11_WRITERS` / `DB_C11_READERS` | 3 / 10 |
| `DB_C12_CONCURRENCY` | 10 |
| `DB_C13_CONCURRENCY` | 8 |
| `DB_C14_CONCURRENCY` / `DB_C14_MAX_POINTS` | 4 / 6 |

## PostgreSQL 模式

默认 pytest fixture 会创建临时 `sqlite+aiosqlite` 数据库，适合快速回归。若要用 PostgreSQL 跑同一批用例，先启动数据库：

```powershell
docker compose up -d postgres redis
```

然后设置 `TEST_DATABASE_URL`：

```powershell
$env:TEST_DATABASE_URL="postgresql+asyncpg://ai_study:ai_study_pwd@localhost:5432/ai_study_db"
.\.venv\Scripts\python.exe -m pytest -q -s `
  tests\test_db_concurrency_c01_c05.py `
  tests\test_db_concurrency_c06_c11.py `
  tests\test_db_concurrency_c12_c14.py
```

建议 PostgreSQL 模式使用一次性测试库或测试前清空数据。fixture 会执行 `Base.metadata.create_all`，但不会自动删除已有业务数据。

## 完整测试套件说明

仓库中已有部分 `test_integration_*` 和 `test_member_a_core_flow.py` 会直接访问 `TEST_BASE_URL`，默认是 `http://localhost:8000`。运行完整套件前需要先启动 API、PostgreSQL、Redis 和 worker：

```powershell
docker compose up -d --build
.\.venv\Scripts\python.exe -m pytest -q -s
```

如果只想运行本次新增的数据库并发测试，不需要启动真实 API 服务；这些用例使用 FastAPI ASGI test client 和 pytest fixture。
