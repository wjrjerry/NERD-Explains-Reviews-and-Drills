# 真实 AI 验收测试报告

测试日期：2026-06-14  
测试目标：验证后端真实 OpenAI-compatible AI Provider 配置与 AI 学习闭环  
测试 Provider：DeepSeek OpenAI-compatible API  
模型：`deepseek-v4-flash`

> 安全说明：本报告不记录真实 API Key。真实 Key 只应放在本地 `.env` 或临时环境变量中，不应提交到 Git。

## 1. 本次新增测试脚本

| 文件 | 用途 |
|---|---|
| `tests/test_real_ai_provider_smoke.py` | 直接调用 `app.services.llm_service.chat_completion()`，验证真实 Provider 的 API Key、Base URL、模型名、请求格式和响应解析是否可用 |
| `tests/test_real_ai_acceptance.py` | 通过后端 HTTP 接口执行真实 AI 业务验收，覆盖 QA、QA 历史、AI 出题、自测主观题评分、复习计划生成 |

两份测试均默认跳过，只有设置：

```bash
RUN_REAL_AI_ACCEPTANCE=1
```

才会实际调用真实 AI，避免日常回归测试误触发真实 API 调用和费用。

## 2. 测试配置

真实 AI 验收需要以下环境变量：

```env
RUN_REAL_AI_ACCEPTANCE=1
AI_PROVIDER=openai-compatible
AI_API_KEY=<your-api-key>
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
AI_TIMEOUT_SECONDS=30
```

说明：

1. 后端 `llm_service` 会将 `AI_BASE_URL=https://api.deepseek.com` 自动拼接为 `https://api.deepseek.com/chat/completions`。
2. 测试只断言响应结构、非空字段和业务记录可持续流转，不断言模型输出的具体文本。
3. `knowledge/extract` 当前主要是本地规则生成，不作为真实 AI Provider 的重点验收对象。

## 3. 测试收集结果

执行：

```bash
pytest --collect-only -q tests/test_real_ai_provider_smoke.py tests/test_real_ai_acceptance.py
```

结果：

```text
tests/test_real_ai_acceptance.py: 1
tests/test_real_ai_provider_smoke.py: 1
```

结论：新增真实 AI 验收测试共 2 条，pytest 可正常发现和加载。

## 4. Provider 直连 Smoke 测试结果

执行：

```bash
RUN_REAL_AI_ACCEPTANCE=1 \
AI_PROVIDER=openai-compatible \
AI_API_KEY=<masked> \
AI_BASE_URL=https://api.deepseek.com \
AI_MODEL=deepseek-v4-flash \
AI_TIMEOUT_SECONDS=30 \
pytest -s -q tests/test_real_ai_provider_smoke.py
```

结果：

```text
.
1 passed
```

结论：

1. DeepSeek API Key 可用。
2. `AI_BASE_URL=https://api.deepseek.com` 可用。
3. `AI_MODEL=deepseek-v4-flash` 可用。
4. 后端 `llm_service` 的 OpenAI-compatible 请求格式可用。
5. 返回内容可被后端成功解析为 assistant message。

## 5. 后端 HTTP 真实 AI 验收测试结果

### 5.1 初次执行问题

初次在 Codex 所在 WSL 环境执行完整 HTTP 验收时失败：

```text
1 failed
```

失败原因：

```text
urllib.error.URLError: <urlopen error [Errno 111] Connection refused>
```

失败位置：

```text
POST http://localhost:8000/auth/register
```

结论：本次失败不是 AI Provider 失败，也不是后端业务断言失败，而是当前执行环境无法访问 `localhost:8000` 后端 API 服务。

随后在可操作 Docker 的 WSL 终端中检查容器环境时，发现后端容器仍然使用 mock 配置：

```text
AI_PROVIDER=mock
AI_BASE_URL=
AI_MODEL=
```

原因是容器启动时读取到的 `.env` 仍为 mock，或修改 `.env` 后容器尚未重新创建。修复方式是将 `.env` 改为真实 AI 配置，并重新启动容器。

### 5.2 最终执行结果

修复 `.env` 并重启后端容器后，在 WSL 中执行：

```bash
pytest -s -q tests/test_real_ai_acceptance.py
```

结果：

```text
.
```

pytest 中每个 `.` 表示一条测试用例通过。本文件包含 1 条完整 HTTP 真实 AI 验收测试，因此最终结果为：

```text
1 passed
```

结论：后端 HTTP 真实 AI 验收测试最终通过。

本条测试通过后，说明以下真实 AI 链路已通过后端接口完成：

1. 注册/登录测试用户。
2. 创建复习目标。
3. 上传并解析 TXT 资料。
4. 调用真实 AI 完成 `/qa/ask` 问答。
5. 查询 QA 历史，并验证记录中的 AI Provider/Model 信息。
6. 调用真实 AI 完成 `/questions/generate` 出题。
7. 提交自测，并触发主观题真实 AI 评分。
8. 基于目标和错题生成复习计划。
9. 验证响应结构、非空字段和业务流程可持续流转。

## 6. 推荐复跑步骤

确认 `.env` 中配置真实 AI：

```env
AI_PROVIDER=openai-compatible
AI_API_KEY=<your-api-key>
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
AI_TIMEOUT_SECONDS=30
```

重启服务并执行迁移：

```bash
docker compose up --build -d --force-recreate
docker compose exec api alembic upgrade heads
```

确认容器中的 AI 配置：

```bash
docker compose exec api sh -lc 'printf "AI_PROVIDER=%s\nAI_BASE_URL=%s\nAI_MODEL=%s\n" "$AI_PROVIDER" "$AI_BASE_URL" "$AI_MODEL"'
```

期望输出：

```text
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
```

运行完整真实 AI 验收：

```bash
pytest -s -q tests/test_real_ai_acceptance.py
```

如需显式启用测试开关：

```bash
RUN_REAL_AI_ACCEPTANCE=1 pytest -s -q tests/test_real_ai_acceptance.py
```

## 7. 验收结论

本次真实 AI 验收分为两层：

1. Provider 直连 smoke：已通过，证明 DeepSeek 真实 AI 配置和后端 `llm_service` 调用方式可用。
2. 后端 HTTP 业务闭环：最终已通过，证明真实 AI 问答、AI 出题、主观题评分和复习计划生成均可通过后端接口完成。

最终结论：

```text
真实 AI Provider 配置可用，后端真实 AI 学习闭环验收通过。
```
