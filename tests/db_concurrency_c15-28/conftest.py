"""
Shared fixtures for DB-C15 through DB-C28 concurrency tests.

These tests reuse the parent tests/conftest.py fixture chain:
  event_loop -> test_engine -> async_session_factory -> client

All tests use the httpx.AsyncClient with ASGI transport targeting an in-memory
SQLite database. For PostgreSQL-level concurrency validation, run via Docker.
"""

import os

# Ensure test environment variables are set before any app imports
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

# Re-export parent fixtures so pytest can find them
# The actual fixtures come from tests/conftest.py via pytest's conftest discovery.
# We add the parent tests/ directory to the path so pytest can find conftest.py there.

import sys
from pathlib import Path

_parent = Path(__file__).resolve().parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))
