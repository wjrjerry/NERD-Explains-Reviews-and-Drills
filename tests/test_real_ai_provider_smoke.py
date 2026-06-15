import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_AI_ACCEPTANCE") != "1",
    reason="set RUN_REAL_AI_ACCEPTANCE=1 to call the real AI provider",
)


def test_real_ai_provider_chat_completion_smoke() -> None:
    """Directly verify the configured OpenAI-compatible provider.

    This is intentionally smaller than the HTTP acceptance flow. It proves that
    the API key, base URL, model name, timeout, request shape, and response
    parsing work with app.services.llm_service.
    """
    assert os.getenv("AI_PROVIDER") == "openai-compatible"
    assert os.getenv("AI_API_KEY")
    assert os.getenv("AI_BASE_URL")
    assert os.getenv("AI_MODEL")

    from app.services import llm_service

    answer = llm_service.chat_completion(
        system_prompt="你是一个简洁的测试助手。只回答一句话。",
        user_prompt="请回答：后端真实 AI Provider 连通性是否正常？",
        task="real_ai_provider_smoke",
    )

    assert isinstance(answer, str)
    assert answer.strip()
