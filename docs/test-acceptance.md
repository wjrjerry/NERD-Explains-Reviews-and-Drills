# 测试验收交付包（Test Acceptance Package）

目的：为评审人员提供一套可重复、可验证的验收步骤、示例命令和需要提交的证据清单，便于证明后端功能是否满足 `docs/backend-team-division.md` 中的验收要点。

**一、总体要求**
- 提交内容：`pytest` 报告（junit/xml 或 html）、关键接口的示例请求/响应（curl 或 Postman/Apifox 导出）、必要时的 DB 查询或迁移日志。  
- 评审方式：自动化测试优先；对 UI/人工可视部分，提供截图或示例响应。

**二、运行与收集证据（本地）**

1) 建议准备（在干净虚拟环境中）：

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx aiosqlite
```

2) 运行测试并生成 JUnit 报告：

```bash
pytest -q --junitxml=artifacts/junit.xml
pytest -q --html=artifacts/report.html  # 可选（需要 pytest-html）
```

3) 收集关键 API 示例（示例流程）：
- 注册用户、登录并保存 `access_token`。  
- 创建课程/考试目标。  
- 上传 TXT 文件（或 PDF/图片示例），调用 `/materials/{id}/parse`。  
- 基于已解析资料调用 `/qa/ask`，保存请求/响应。  

示例：注册并登录获取 token（curl）：

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"tester","password":"password123"}'

curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"tester","password":"password123"}'
# 从返回 JSON 中复制 data.token.access_token
```

示例：上传 TXT（httpie 写法，等同 curl）

```bash
http --form POST http://localhost:8000/materials "Authorization:Bearer $TOKEN" target_id=1 file@./sample.txt
```

示例：解析并提问

```bash
curl -X POST http://localhost:8000/materials/123/parse -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8000/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"material_id":123, "question":"关键点是什么？"}'
```

将上述命令的 stdout/stderr 和响应 JSON 保存为 `artifacts/` 下的样例文件。

**三、逐项验收清单与证据要求（对应 docs/backend-team-division.md 的 10 点）**

1. 用户注册登录
- 验证动作：运行 `tests/test_auth.py` 或使用 curl 注册并登陆。  
- 证据：`pytest` 成功（junit.xml 中相应测试通过），以及 login 返回包含 `access_token` 的示例响应。

2. 登录后创建课程/考试目标
- 验证动作：`POST /study-targets`（带 Authorization）并 `GET /study-targets`。  
- 证据：测试通过截图或示例请求/响应。

3. 上传资料并看到解析状态
- 验证动作：上传 TXT（或 PDF/图片），调用 `POST /materials/{id}/parse`，然后 `GET /materials/{id}/preview` 或 `GET /materials` 查看 `parse_status`。  
- 证据：上传响应、parse 响应与 `parse_status` 为 `parsed` 的记录快照或测试断言。

4. 资料解析后生成知识提炼结果（若存在接口）
- 验证动作：调用知识提炼接口或直接运行 `ai_service.generate_knowledge(parsed_text)` 的集成测试。  
- 最低证据：返回 JSON 包含 `summary`、`outline`、`keywords` 字段的示例。

5. 基于资料进行问答
- 验证动作：`POST /qa/ask`（已解析的 material）并断言返回 `answer`。  
- 证据：测试通过（见 `tests/test_ai_flow.py`）与示例请求/响应。

6. 生成自测题
- 验证动作：调用题目生成接口（如 `POST /questions/generate` 或服务方法），断言题目数量、类型和选项结构。  
- 若接口未实现：记录为阻塞项并创建 Issue（见下文）。  

7. 提交答案并返回评分与解析
- 验证动作：调用 `POST /tests/submit`，断言返回总分、每题结果及错题数。  
- 若路由未实现：记录为阻塞项并提供最小输入/输出规范。

8. 错题自动进入错题本
- 验证动作：提交错误答案后 `GET /wrong-questions` 并断言该错题存在（用户隔离）。  

9. 根据错题与考试日期生成复习计划
- 验证动作：`POST /review-plans/generate` 并断言返回任务列表与时间分配。  

10. 管理员查看用户、资料、AI 调用记录和异常任务
- 验证动作：管理员使用 admin token 访问管理接口，普通用户访问同一路由得到 403。  
- 证据：管理员请求示例/响应；如需 AI 调用日志，需包含 `ai_call_logs` 表和迁移日志（见下文）。

**四、未实现功能建议与 Issue 模板**

对于未实现或尚不完整的点，请创建 Issue 并包含以下内容：

- 标题示例：`实现 /tests/submit：提交自测并返回评分与错题写入`。  
- 描述：业务场景、最小请求样例、预期响应 JSON（字段名与类型）、错误情形与 HTTP 状态码。  
- 验收条件（acceptance criteria）：列出测试用例要通过的断言（例如：错题数量更新、wrong_questions 表插入等）。

示例最小响应规范（`/tests/submit`）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "score": 80,
    "total": 100,
    "wrong_count": 2,
    "details": [ /* per-question result */ ]
  }
}
```

**五、CI 建议（可选）**

建议在 `.github/workflows/test.yml` 中添加如下步骤：

```yaml
name: Run tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
          POSTGRES_DB: test_db
        ports: [5432]
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 10s --health-timeout 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx aiosqlite
      - name: Run migrations (optional)
        run: alembic upgrade head
      - name: Run tests
        run: pytest -q --junitxml=artifacts/junit.xml
      - name: Upload junit
        uses: actions/upload-artifact@v4
        with:
          name: pytest-junit
          path: artifacts/junit.xml
```

注：若 CI 中使用 Postgres，请确保 `app/core/config.py` 可从环境读取 `database_url` 并覆盖为 CI 提供的 Postgres，或使用 sqlite 直接运行测试（当前测试夹具使用 sqlite，方便快速 CI）。

**六、验收交付包清单（提交给评审）**

- `artifacts/junit.xml` 或 `artifacts/report.html`（pytest 报告）  
- 关键 API 的请求/响应示例（`artifacts/http_samples/`）  
- 如执行迁移：`alembic` 迁移文件与 CI 运行日志  
- `docs/test-acceptance.md`（本文件）  

---

如需，我可以：
- 把上面的 GitHub Actions 文件草案加入仓库（创建 `.github/workflows/test.yml`）。  
- 或者仅生成 `docs/test-acceptance.md`（已完成）并把 `requirements-dev.txt` 建议写入。  

请选择要我接着做的下一步（`add-ci` / `add-dev-reqs` / `done`）。
