"""Schemas for user-visible AI token usage and local billing."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.ai_call_log import AiCallStatus


class AiUsageLogItem(BaseModel):
    """One AI provider call shown to the current user."""

    id: int
    target_id: int | None = None
    material_id: int | None = None
    feature: str
    provider: str
    model: str | None = None
    status: AiCallStatus
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    reasoning_tokens: int | None = None
    estimated_cost: Decimal = Field(description="本平台按 token 单价估算的费用")
    currency: str
    billing_policy_version: str
    latency_ms: int
    created_at: str
    error_message: str | None = None


class AiUsageFeatureSummary(BaseModel):
    """Aggregated usage for one feature."""

    feature: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    currency: str


class AiUsageSummary(BaseModel):
    """Current user's total AI usage summary."""

    total_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    currency: str
    billing_policy_version: str
    by_feature: list[AiUsageFeatureSummary]
