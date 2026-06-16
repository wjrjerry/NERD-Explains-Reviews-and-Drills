from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.study_target import StudyTarget
from app.models.user import User, UserRole
from tests.concurrency_helpers import (
    api_ok,
    auth_headers,
    create_logged_in_user,
    create_study_target,
    env_int,
    no_server_error,
    register_user,
    run_concurrently,
    unique_name,
)


@pytest.mark.asyncio
async def test_db_c01_concurrent_register_same_username(client, async_session_factory):
    concurrency = env_int("DB_C01_CONCURRENCY", 1000)
    username = unique_name("same_user")

    async def register_same(index: int):
        return await client.post(
            "/auth/register",
            json={
                "username": username,
                "password": "password123",
                "display_name": f"same user {index}",
            },
        )

    report, responses = await run_concurrently(
        case_id="DB-C01",
        module="auth register unique username",
        code_paths=[
            "app/routers/auth.py",
            "app/services/auth_service.py",
            "app/repositories/user_repository.py",
            "app/models/user.py",
        ],
        concurrency=concurrency,
        operation=register_same,
        is_success=no_server_error,
        notes="Concurrent registration with the same username should be handled by the unique constraint.",
    )

    assert report.success_count == concurrency
    assert sum(1 for response in responses if not isinstance(response, Exception) and api_ok(response)) == 1
    async with async_session_factory() as db:
        count = await db.scalar(select(func.count()).select_from(User).where(User.username == username))
    assert count == 1


@pytest.mark.asyncio
async def test_db_c02_concurrent_login_updates_last_login(client, async_session_factory):
    concurrency = env_int("DB_C02_CONCURRENCY", 1000)
    username = unique_name("login_user")
    await register_user(client, username=username)

    async def login(_index: int):
        return await client.post(
            "/auth/login",
            json={"username": username, "password": "password123"},
        )

    report, _responses = await run_concurrently(
        case_id="DB-C02",
        module="auth login last_login_at update",
        code_paths=[
            "app/routers/auth.py",
            "app/services/auth_service.py",
            "app/repositories/user_repository.py",
            "app/models/user.py",
        ],
        concurrency=concurrency,
        operation=login,
        is_success=api_ok,
        notes="Concurrent login should keep all requests successful and leave a last_login_at timestamp.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.username == username))
    assert user is not None
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_db_c03_concurrent_admin_user_status_updates(client, async_session_factory):
    concurrency = env_int("DB_C03_CONCURRENCY", 1000)
    admin_token, admin_user, admin_username = await create_logged_in_user(client, prefix="admin_user")
    target_token, target_user, _target_username = await create_logged_in_user(client, prefix="status_user")

    async with async_session_factory() as db:
        admin = await db.scalar(select(User).where(User.username == admin_username))
        assert admin is not None
        admin.role = UserRole.admin
        db.add(admin)
        await db.commit()

    admin_token, _admin_user = await client.post(
        "/auth/login",
        json={"username": admin_username, "password": "password123"},
    ), None
    assert api_ok(admin_token), admin_token.text
    admin_headers = auth_headers(admin_token.json()["data"]["token"]["access_token"])
    assert target_token
    assert admin_user["id"] != target_user["id"]

    async def update_status(index: int):
        return await client.patch(
            f"/admin/users/{target_user['id']}/status",
            json={"is_active": index % 2 == 0},
            headers=admin_headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C03",
        module="admin user active status",
        code_paths=[
            "app/routers/admin.py",
            "app/dependencies/auth.py",
            "app/repositories/user_repository.py",
            "app/repositories/admin_log_repository.py",
            "app/models/user.py",
        ],
        concurrency=concurrency,
        operation=update_status,
        is_success=api_ok,
        notes="Concurrent enable/disable writes should not produce server errors or corrupt the user row.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.id == target_user["id"]))
    assert user is not None
    assert isinstance(user.is_active, bool)


@pytest.mark.asyncio
async def test_db_c04_concurrent_study_target_creation(client, async_session_factory):
    concurrency = env_int("DB_C04_CONCURRENCY", 1000)
    token, user, _username = await create_logged_in_user(client, prefix="target_user")
    headers = auth_headers(token)

    async def create_target(index: int):
        return await client.post(
            "/study-targets",
            json={
                "title": f"concurrent target {index} {unique_name('case')}",
                "subject": "database concurrency",
                "target_type": "exam",
                "exam_date": "2026-07-01",
            },
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C04",
        module="study target create",
        code_paths=[
            "app/routers/study_targets.py",
            "app/services/study_target_service.py",
            "app/repositories/study_target_repository.py",
            "app/models/study_target.py",
        ],
        concurrency=concurrency,
        operation=create_target,
        is_success=api_ok,
        notes="One user creates many study targets concurrently.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(StudyTarget)
            .where(StudyTarget.user_id == user["id"], StudyTarget.is_deleted.is_(False))
        )
    assert count >= concurrency


@pytest.mark.asyncio
async def test_db_c05_concurrent_study_target_update_delete_read(client, async_session_factory):
    concurrency = env_int("DB_C05_CONCURRENCY", 1000)
    token, user, _username = await create_logged_in_user(client, prefix="target_race_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("race_target"))

    async def mutate_or_read(index: int):
        if index == 0:
            return await client.delete(f"/study-targets/{target['id']}", headers=headers)
        if index % 3 == 0:
            return await client.get(f"/study-targets/{target['id']}", headers=headers)
        return await client.patch(
            f"/study-targets/{target['id']}",
            json={"title": f"race title {index}"},
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C05",
        module="study target update/delete/read race",
        code_paths=[
            "app/routers/study_targets.py",
            "app/services/study_target_service.py",
            "app/repositories/study_target_repository.py",
            "app/models/study_target.py",
        ],
        concurrency=concurrency,
        operation=mutate_or_read,
        is_success=no_server_error,
        notes="Mixed PATCH/DELETE/GET should settle on a soft-deleted target without 5xx responses.",
    )

    assert report.success_count == concurrency
    assert user["id"] == target["user_id"]
    async with async_session_factory() as db:
        row = await db.scalar(select(StudyTarget).where(StudyTarget.id == target["id"]))
    assert row is not None
    assert row.is_deleted is True
