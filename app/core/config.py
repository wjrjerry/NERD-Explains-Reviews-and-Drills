from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI智能备考复习平台"
    app_env: str = "dev"
    debug: bool = True

    database_url: str
    redis_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4173,"
        "http://127.0.0.1:4173"
    )

    ai_provider: str = "mock"
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
