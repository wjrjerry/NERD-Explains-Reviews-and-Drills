import asyncio
import os
from typing import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set required environment variables BEFORE any app imports to avoid Pydantic validation errors
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine(tmp_path_factory) -> AsyncGenerator:
    """Create a temporary sqlite+aiosqlite engine for tests and create tables."""
    configured_db_url = os.getenv("TEST_DATABASE_URL")
    if configured_db_url:
        db_url = configured_db_url
    else:
        db_dir = tmp_path_factory.mktemp("data")
        db_file = db_dir / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_file}"

    # Import Base and models so metadata is populated
    from app.db.base import Base

    # Ensure all model modules are imported so they are registered on Base
    import app.models.user
    import app.models.study_target
    import app.models.material
    import app.models.material_structure
    import app.models.parse_task
    import app.models.admin_log
    import app.models.knowledge
    import app.models.knowledge_job
    import app.models.question
    import app.models.test_record
    import app.models.wrong_question
    import app.models.review_plan
    import app.models.qa
    import app.models.knowledge_point
    import app.models.ai_call_log

    connect_args = {}
    if db_url.startswith("sqlite+aiosqlite"):
        connect_args = {"timeout": 30}

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        connect_args=connect_args,
    )

    async with engine.begin() as conn:
        if db_url.startswith("sqlite+aiosqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def async_session_factory(test_engine) -> async_sessionmaker:
    """Create a reusable async sessionmaker bound to the test engine."""
    maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Patch the application's AsyncSessionLocal so code using it (e.g. health endpoints)
    import app.db.session as session_module

    session_module.AsyncSessionLocal = maker

    yield maker


@pytest.fixture
async def client(async_session_factory, tmp_path, monkeypatch) -> AsyncGenerator:
    """Provide an `httpx.AsyncClient` for the FastAPI app with DB dependency overridden.

    Also redirect uploads to a temporary directory so tests do not write into the repo.
    """
    from httpx import AsyncClient

    # Patch upload dir to a temp location
    import app.core.config as config

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(config.settings, "upload_dir", str(upload_dir))

    # Ensure the app uses the test sessionmaker via dependency override
    from app.main import app as fastapi_app
    from app.db.session import AsyncSessionLocal, get_db

    async def _get_test_db():
        async with AsyncSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _get_test_db

    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test"
    ) as ac:
        yield ac
