"""Minimal real LLM provider integration.

The project keeps mock AI as the default. When AI_PROVIDER is configured as
"openai-compatible", this service calls a Chat Completions compatible endpoint.
That shape works for OpenAI-compatible providers and many course-project friendly
LLM gateways.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import json
import logging
import time
from urllib import error, request

from app.core.config import settings

# Use Uvicorn's error logger so application logs are visible in
# `docker compose logs api` without extra logging configuration.
logger = logging.getLogger("uvicorn.error")


class LlmServiceError(RuntimeError):
    """Raised when real LLM configuration or provider calls fail."""


@dataclass(frozen=True)
class LlmCallTrace:
    """Metadata for one Chat Completions provider call."""

    task: str
    provider: str
    model: str | None
    status: str
    latency_ms: int
    prompt_chars: int
    completion_chars: int
    http_status_code: int | None = None
    error_message: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    reasoning_tokens: int | None = None


_call_traces: ContextVar[list[LlmCallTrace] | None] = ContextVar(
    "llm_call_traces",
    default=None,
)


def _append_call_trace(trace: LlmCallTrace) -> None:
    """Append call metadata to the current context for later persistence."""
    traces = _call_traces.get()
    if traces is None:
        traces = []
    _call_traces.set([*traces, trace])


def pop_call_traces() -> list[LlmCallTrace]:
    """Return and clear LLM call traces collected in the current context."""
    traces = _call_traces.get() or []
    _call_traces.set([])
    return traces


def _to_int(value: object) -> int | None:
    """Convert provider usage values to int when possible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_success_trace(
    *,
    task: str,
    model: str,
    elapsed_ms: int,
    prompt_chars: int,
    content: str,
    data: dict[str, object],
) -> LlmCallTrace:
    """Extract OpenAI-compatible usage metadata from a successful response."""
    usage = data.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    completion_details = usage.get("completion_tokens_details")
    if not isinstance(completion_details, dict):
        completion_details = {}

    return LlmCallTrace(
        task=task,
        provider=settings.ai_provider,
        model=model,
        status="success",
        latency_ms=elapsed_ms,
        prompt_chars=prompt_chars,
        completion_chars=len(content),
        prompt_tokens=_to_int(usage.get("prompt_tokens")),
        completion_tokens=_to_int(usage.get("completion_tokens")),
        total_tokens=_to_int(usage.get("total_tokens")),
        prompt_cache_hit_tokens=_to_int(usage.get("prompt_cache_hit_tokens")),
        prompt_cache_miss_tokens=_to_int(usage.get("prompt_cache_miss_tokens")),
        reasoning_tokens=_to_int(completion_details.get("reasoning_tokens")),
    )


def _build_failed_trace(
    *,
    task: str,
    model: str | None,
    elapsed_ms: int,
    prompt_chars: int,
    error_message: str,
    http_status_code: int | None = None,
) -> LlmCallTrace:
    """Build failure metadata for persistence when provider calls fail."""
    return LlmCallTrace(
        task=task,
        provider=settings.ai_provider,
        model=model,
        status="failed",
        latency_ms=elapsed_ms,
        prompt_chars=prompt_chars,
        completion_chars=0,
        http_status_code=http_status_code,
        error_message=error_message[:2000],
    )


def _chat_completions_url(base_url: str) -> str:
    """Normalize configured base URL to a chat completions endpoint."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _require_real_ai_settings() -> tuple[str, str, str]:
    """Return required real AI settings or raise a clear configuration error."""
    if not settings.ai_api_key:
        raise LlmServiceError("AI_API_KEY is required when AI_PROVIDER is not mock.")
    if not settings.ai_base_url:
        raise LlmServiceError("AI_BASE_URL is required when AI_PROVIDER is not mock.")
    if not settings.ai_model:
        raise LlmServiceError("AI_MODEL is required when AI_PROVIDER is not mock.")

    return settings.ai_api_key, settings.ai_base_url, settings.ai_model


def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    task: str = "unknown",
    timeout_seconds: int | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call a Chat Completions compatible API and return assistant text."""
    api_key, base_url, model = _require_real_ai_settings()
    url = _chat_completions_url(base_url)
    started_at = time.perf_counter()
    prompt_chars = len(system_prompt) + len(user_prompt)
    logger.info(
        "AI call started task=%s provider=%s model=%s base_url=%s prompt_chars=%s",
        task,
        settings.ai_provider,
        model,
        base_url,
        prompt_chars,
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds or settings.ai_timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        message = f"LLM provider returned HTTP {exc.code}: {detail}"
        _append_call_trace(
            _build_failed_trace(
                task=task,
                model=model,
                elapsed_ms=elapsed_ms,
                prompt_chars=prompt_chars,
                http_status_code=exc.code,
                error_message=message,
            )
        )
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=http status_code=%s",
            task,
            model,
            elapsed_ms,
            exc.code,
        )
        raise LlmServiceError(message) from exc
    except error.URLError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        message = f"Failed to connect to LLM provider: {exc.reason}"
        _append_call_trace(
            _build_failed_trace(
                task=task,
                model=model,
                elapsed_ms=elapsed_ms,
                prompt_chars=prompt_chars,
                error_message=message,
            )
        )
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=network reason=%s",
            task,
            model,
            elapsed_ms,
            exc.reason,
        )
        raise LlmServiceError(message) from exc
    except TimeoutError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        _append_call_trace(
            _build_failed_trace(
                task=task,
                model=model,
                elapsed_ms=elapsed_ms,
                prompt_chars=prompt_chars,
                error_message="LLM provider request timed out.",
            )
        )
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=timeout",
            task,
            model,
            elapsed_ms,
        )
        raise LlmServiceError("LLM provider request timed out.") from exc

    try:
        data = json.loads(response_body)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        _append_call_trace(
            _build_failed_trace(
                task=task,
                model=model,
                elapsed_ms=elapsed_ms,
                prompt_chars=prompt_chars,
                error_message="LLM provider returned an unexpected response shape.",
            )
        )
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=response_shape",
            task,
            model,
            elapsed_ms,
        )
        raise LlmServiceError("LLM provider returned an unexpected response shape.") from exc

    if not isinstance(content, str) or not content.strip():
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        _append_call_trace(
            _build_failed_trace(
                task=task,
                model=model,
                elapsed_ms=elapsed_ms,
                prompt_chars=prompt_chars,
                error_message="LLM provider returned an empty answer.",
            )
        )
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=empty_answer",
            task,
            model,
            elapsed_ms,
        )
        raise LlmServiceError("LLM provider returned an empty answer.")

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    _append_call_trace(
        _build_success_trace(
            task=task,
            model=model,
            elapsed_ms=elapsed_ms,
            prompt_chars=prompt_chars,
            content=content,
            data=data,
        )
    )
    logger.info(
        "AI call succeeded task=%s model=%s elapsed_ms=%s answer_chars=%s",
        task,
        model,
        elapsed_ms,
        len(content),
    )
    return content.strip()
