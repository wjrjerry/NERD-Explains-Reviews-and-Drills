"""Minimal real LLM provider integration.

The project keeps mock AI as the default. When AI_PROVIDER is configured as
"openai-compatible", this service calls a Chat Completions compatible endpoint.
That shape works for OpenAI-compatible providers and many course-project friendly
LLM gateways.
"""

from __future__ import annotations

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
) -> str:
    """Call a Chat Completions compatible API and return assistant text."""
    api_key, base_url, model = _require_real_ai_settings()
    url = _chat_completions_url(base_url)
    started_at = time.perf_counter()
    logger.info(
        "AI call started task=%s provider=%s model=%s base_url=%s prompt_chars=%s",
        task,
        settings.ai_provider,
        model,
        base_url,
        len(system_prompt) + len(user_prompt),
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
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
        with request.urlopen(req, timeout=settings.ai_timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=http status_code=%s",
            task,
            model,
            elapsed_ms,
            exc.code,
        )
        raise LlmServiceError(f"LLM provider returned HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=network reason=%s",
            task,
            model,
            elapsed_ms,
            exc.reason,
        )
        raise LlmServiceError(f"Failed to connect to LLM provider: {exc.reason}") from exc
    except TimeoutError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
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
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=response_shape",
            task,
            model,
            elapsed_ms,
        )
        raise LlmServiceError("LLM provider returned an unexpected response shape.") from exc

    if not isinstance(content, str) or not content.strip():
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.warning(
            "AI call failed task=%s model=%s elapsed_ms=%s error_type=empty_answer",
            task,
            model,
            elapsed_ms,
        )
        raise LlmServiceError("LLM provider returned an empty answer.")

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "AI call succeeded task=%s model=%s elapsed_ms=%s answer_chars=%s",
        task,
        model,
        elapsed_ms,
        len(content),
    )
    return content.strip()
