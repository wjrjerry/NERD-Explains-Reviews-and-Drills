# AI Provider Setup

## 1. 当前策略

项目默认使用 mock AI：

```text
AI_PROVIDER=mock
```

mock 模式不需要网络和 API Key，适合开发知识提炼、问答、出题、自测等主流程。

当需要初步测试真实 AI 时，可以切换到 OpenAI-compatible Chat Completions 接口：

```text
AI_PROVIDER=openai-compatible
```

当前只有 `POST /qa/ask` 接入了真实 AI 调用入口。知识提炼和出题仍保持 mock，避免第一阶段一次性引入复杂 JSON 输出解析。

## 2. 环境变量

不要把真实 API Key 提交到仓库。请在本地 `.env` 或部署环境中配置：

```text
AI_PROVIDER=openai-compatible
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://example.com/v1
AI_MODEL=your-model-name
AI_TIMEOUT_SECONDS=30
```

`AI_BASE_URL` 可以填写服务根地址，也可以填写完整 chat completions 地址：

```text
https://example.com/v1
https://example.com/v1/chat/completions
```

## 3. 测试方式

启动服务后请求：

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -H "x-user-id: 1" \
  -d '{"material_id": 1, "question": "什么是需求分析？"}'
```

当 `AI_PROVIDER=mock` 时，返回模板化 mock 回答。

当 `AI_PROVIDER=openai-compatible` 且配置正确时，返回真实模型基于 `parsed_text` 生成的回答。

## 4. 错误行为

真实 AI 配置缺失、网络失败、超时或响应格式异常时，`POST /qa/ask` 会返回 HTTP 503，并在 `detail` 中说明原因。

这类错误不会静默 fallback 到 mock，避免把真实集成问题误判为成功。

## 5. 后续计划

后续可逐步扩展：

- 为 AI 知识提炼接入结构化 JSON 输出。
- 为 AI 出题接入结构化 JSON 输出。
- 增加 AI 调用日志和耗时统计。
- 增加额度控制和管理员监控。
