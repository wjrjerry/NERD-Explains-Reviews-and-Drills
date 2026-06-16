from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI智能备考复习平台"
    app_env: str = "dev"
    debug: bool = True

    database_url: str
    redis_url: str
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_task_always_eager: bool = False

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    initial_admin_username: str | None = None
    initial_admin_password: str | None = None
    initial_admin_display_name: str | None = None

    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    ocr_languages: str = "chi_sim+eng"
    ocr_timeout_seconds: int = 30
    ocr_image_scale: float = 1.5
    ocr_binarize_threshold: int = 180
    ocr_min_text_length: int = 10
    ocr_bad_char_ratio: float = 0.35
    pdf_ocr_dpi: int = 200
    pdf_ocr_max_pages: int = 20
    parsed_text_max_chars: int = 20000

    vision_enabled: bool = False
    vision_provider: str = "openrouter"
    vision_api_key: str | None = None
    vision_base_url: str = "https://openrouter.ai/api/v1"
    vision_model: str = "google/gemini-3.1-flash-lite-preview"
    vision_timeout_seconds: int = 60
    vision_max_pages: int = 5
    vision_max_image_bytes: int = 4_000_000
    vision_response_format_json: bool = True
    vision_fallback_on_ocr_failure: bool = True
    vision_fallback_on_low_quality: bool = False

    ai_provider: str = "mock"
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: int = 30
    ai_billing_currency: str = "CNY"
    ai_billing_policy_version: str = "openrouter-qwen3-30b-a3b-instruct-2507-cny-2026-06"
    ai_price_prompt_per_1k_tokens: float = 0.000326
    ai_price_completion_per_1k_tokens: float = 0.001306
    ai_price_cache_hit_prompt_per_1k_tokens: float | None = None
    ai_price_cache_miss_prompt_per_1k_tokens: float | None = None
    ai_price_reasoning_per_1k_tokens: float | None = None

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: Any) -> Any:
        """Accept common environment labels for DEBUG in local shells."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    @field_validator(
        "ai_price_cache_hit_prompt_per_1k_tokens",
        "ai_price_cache_miss_prompt_per_1k_tokens",
        "ai_price_reasoning_per_1k_tokens",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: Any) -> Any:
        """Treat blank optional price settings as unset."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
