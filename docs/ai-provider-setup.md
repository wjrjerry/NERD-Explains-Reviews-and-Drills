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

当前真实 AI 已用于问答、知识提炼、知识图谱、出题、主观题评分和复习计划等学习闭环能力。

## 2. 环境变量

不要把真实 API Key 提交到仓库。请在本地 `.env` 或部署环境中配置：

```text
AI_PROVIDER=openai-compatible
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://example.com/v1
AI_MODEL=your-model-name
AI_TIMEOUT_SECONDS=60
```

`AI_BASE_URL` 可以填写服务根地址，也可以填写完整 chat completions 地址：

```text
https://example.com/v1
https://example.com/v1/chat/completions
```

OpenRouter 示例：

```text
AI_PROVIDER=openai-compatible
AI_API_KEY=sk-or-v1-...
AI_BASE_URL=https://openrouter.ai/api/v1
AI_MODEL=qwen/qwen3-30b-a3b-instruct-2507
AI_TIMEOUT_SECONDS=60
```

已验证可用于文本学习链路的 OpenRouter 模型包括：

- `qwen/qwen3-30b-a3b-instruct-2507`
- `deepseek/deepseek-chat-v3.1`
- `meta-llama/llama-3.3-70b-instruct`

如果看到 `This model is not available in your region`，说明 OpenRouter 或上游模型在当前区域不可用，通常需要更换 `AI_MODEL`，不是后端接口路径问题。

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

真实 AI 配置缺失、网络失败、超时或响应格式异常时，对应接口会返回明确错误，并在 AI 调用日志中记录失败原因。

这类错误不会静默 fallback 到 mock，避免把真实集成问题误判为成功。

## 5. 使用建议

- 文本问答、知识提炼、出题建议优先选择稳定的文本模型。
- 图片/PDF 视觉解析使用 `VISION_MODEL`，不要直接复用只支持文本的 `AI_MODEL`。
- 更换 `.env` 后需要重新创建 API 容器：`docker compose up -d --build api`。
