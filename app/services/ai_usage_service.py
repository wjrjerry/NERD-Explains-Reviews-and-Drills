"""AI usage logging and local token-based billing service."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_call_log import AiCallLog, AiCallStatus
from app.repositories.ai_call_log_repository import AiCallLogRepository
from app.schemas.ai_usage import AiUsageFeatureSummary, AiUsageLogItem, AiUsageSummary
from app.services import llm_service
from app.services.llm_service import LlmCallTrace


def _decimal(value: float | int | None) -> Decimal:
    """Convert a numeric setting to Decimal for stable cost calculation."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def estimate_cost(trace: LlmCallTrace) -> Decimal:
    """Estimate local cost from token usage using project-configured prices.

    Prices are configured per 1000 tokens. This is intentionally a local
    platform policy and does not need to exactly match a provider bill.
    """
    prompt_tokens = trace.prompt_tokens or 0
    completion_tokens = trace.completion_tokens or 0
    cache_hit_tokens = trace.prompt_cache_hit_tokens or 0
    cache_miss_tokens = trace.prompt_cache_miss_tokens or 0
    reasoning_tokens = trace.reasoning_tokens or 0

    if cache_hit_tokens or cache_miss_tokens:
        prompt_cost = (
            _decimal(settings.ai_price_cache_hit_prompt_per_1k_tokens)
            * Decimal(cache_hit_tokens)
            + _decimal(settings.ai_price_cache_miss_prompt_per_1k_tokens)
            * Decimal(cache_miss_tokens)
        ) / Decimal(1000)
        remaining_prompt_tokens = max(prompt_tokens - cache_hit_tokens - cache_miss_tokens, 0)
        prompt_cost += (
            _decimal(settings.ai_price_prompt_per_1k_tokens)
            * Decimal(remaining_prompt_tokens)
        ) / Decimal(1000)
    else:
        prompt_cost = (
            _decimal(settings.ai_price_prompt_per_1k_tokens) * Decimal(prompt_tokens)
        ) / Decimal(1000)

    completion_billable_tokens = max(completion_tokens - reasoning_tokens, 0)
    completion_cost = (
        _decimal(settings.ai_price_completion_per_1k_tokens)
        * Decimal(completion_billable_tokens)
    ) / Decimal(1000)
    reasoning_cost = (
        _decimal(settings.ai_price_reasoning_per_1k_tokens) * Decimal(reasoning_tokens)
    ) / Decimal(1000)

    return (prompt_cost + completion_cost + reasoning_cost).quantize(Decimal("0.000001"))


def _row_from_trace(
    trace: LlmCallTrace,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
) -> dict[str, object]:
    """Map one collected LLM call trace to an AiCallLog row."""
    return {
        "user_id": user_id,
        "target_id": target_id,
        "material_id": material_id,
        "feature": trace.task,
        "provider": trace.provider,
        "model": trace.model,
        "status": AiCallStatus(trace.status),
        "http_status_code": trace.http_status_code,
        "error_message": trace.error_message,
        "prompt_tokens": trace.prompt_tokens,
        "completion_tokens": trace.completion_tokens,
        "total_tokens": trace.total_tokens,
        "prompt_cache_hit_tokens": trace.prompt_cache_hit_tokens,
        "prompt_cache_miss_tokens": trace.prompt_cache_miss_tokens,
        "reasoning_tokens": trace.reasoning_tokens,
        "estimated_cost": estimate_cost(trace),
        "currency": settings.ai_billing_currency,
        "billing_policy_version": settings.ai_billing_policy_version,
        "latency_ms": trace.latency_ms,
        "prompt_chars": trace.prompt_chars,
        "completion_chars": trace.completion_chars,
    }


async def record_pending_traces(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None = None,
    material_id: int | None = None,
) -> list[AiCallLog]:
    """Persist and clear LLM traces collected during the current request."""
    traces = llm_service.pop_call_traces()
    if not traces:
        return []

    rows = [
        _row_from_trace(
            trace,
            user_id=user_id,
            target_id=target_id,
            material_id=material_id,
        )
        for trace in traces
    ]
    return await AiCallLogRepository.create_many(db, rows=rows)


def clear_pending_traces() -> None:
    """Drop any stale traces before starting one business operation."""
    llm_service.pop_call_traces()


def _to_log_item(log: AiCallLog) -> AiUsageLogItem:
    """Map an AI call log row to public response schema."""
    return AiUsageLogItem(
        id=log.id,
        target_id=log.target_id,
        material_id=log.material_id,
        feature=log.feature,
        provider=log.provider,
        model=log.model,
        status=log.status,
        prompt_tokens=log.prompt_tokens,
        completion_tokens=log.completion_tokens,
        total_tokens=log.total_tokens,
        prompt_cache_hit_tokens=log.prompt_cache_hit_tokens,
        prompt_cache_miss_tokens=log.prompt_cache_miss_tokens,
        reasoning_tokens=log.reasoning_tokens,
        estimated_cost=log.estimated_cost,
        currency=log.currency,
        billing_policy_version=log.billing_policy_version,
        latency_ms=log.latency_ms,
        created_at=log.created_at.isoformat(),
        error_message=log.error_message,
    )


async def list_usage_logs(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
    feature: str | None,
    status: AiCallStatus | None,
    start_at: datetime | None,
    end_at: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[AiUsageLogItem], int]:
    """Return paginated AI call logs for the current user."""
    logs, total = await AiCallLogRepository.list_logs(
        db,
        user_id=user_id,
        target_id=target_id,
        material_id=material_id,
        feature=feature,
        status=status,
        start_at=start_at,
        end_at=end_at,
        page=page,
        page_size=page_size,
    )
    return [_to_log_item(log) for log in logs], total


async def summarize_usage(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> AiUsageSummary:
    """Return token usage and estimated local cost summary for a user."""
    data = await AiCallLogRepository.summarize(
        db,
        user_id=user_id,
        target_id=target_id,
        material_id=material_id,
        start_at=start_at,
        end_at=end_at,
    )
    return AiUsageSummary(
        total_calls=int(data["total_calls"]),
        prompt_tokens=int(data["prompt_tokens"]),
        completion_tokens=int(data["completion_tokens"]),
        total_tokens=int(data["total_tokens"]),
        estimated_cost=data["estimated_cost"],
        currency=settings.ai_billing_currency,
        billing_policy_version=settings.ai_billing_policy_version,
        by_feature=[
            AiUsageFeatureSummary(
                feature=str(feature),
                calls=int(calls),
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                total_tokens=int(total_tokens),
                estimated_cost=estimated_cost,
                currency=settings.ai_billing_currency,
            )
            for (
                feature,
                calls,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                estimated_cost,
            ) in data["by_feature"]
        ],
    )
