from decimal import Decimal

from app.core.config import settings
from app.services.ai_usage_service import estimate_cost
from app.services.llm_service import LlmCallTrace


def test_estimate_cost_uses_configured_nonzero_prices(monkeypatch):
    monkeypatch.setattr(settings, "ai_price_prompt_per_1k_tokens", 0.00004815)
    monkeypatch.setattr(settings, "ai_price_completion_per_1k_tokens", 0.0001931)
    monkeypatch.setattr(settings, "ai_price_reasoning_per_1k_tokens", None)
    monkeypatch.setattr(settings, "ai_price_cache_hit_prompt_per_1k_tokens", None)
    monkeypatch.setattr(settings, "ai_price_cache_miss_prompt_per_1k_tokens", None)

    cost = estimate_cost(
        LlmCallTrace(
            task="qa",
            provider="openai-compatible",
            model="qwen/qwen3-30b-a3b-instruct-2507",
            status="success",
            latency_ms=1200,
            prompt_chars=1000,
            completion_chars=500,
            prompt_tokens=1000,
            completion_tokens=1000,
            total_tokens=2000,
        )
    )

    assert cost == Decimal("0.000241")
