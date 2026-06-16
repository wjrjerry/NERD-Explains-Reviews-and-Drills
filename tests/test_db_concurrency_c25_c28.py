from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models.ai_call_log import AiCallLog
from app.models.user import User, UserRole
from tests.concurrency_helpers import (
    api_ok,
    auth_headers,
    create_logged_in_user,
    create_study_target,
    env_int,
    no_server_error,
    run_concurrently,
    unique_name,
    upload_text_material,
)
from tests.test_db_concurrency_c06_c11 import _mark_material_parsed


async def _prepare_learning_target(client, async_session_factory):
    token, user, username = await create_logged_in_user(client, prefix="admin_concurrency_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("admin_target"))
    material = await upload_text_material(
        client,
        headers=headers,
        target_id=target["id"],
        auto_parse=False,
        text=(
            "# Admin and Export Concurrency\n"
            "AI usage logs, exports, and health checks should stay responsive during mixed traffic.\n"
        ),
    )
    await _mark_material_parsed(async_session_factory, material["id"])
    return token, headers, user, username, target, material


async def _promote_user_to_admin(async_session_factory, username: str) -> None:
    async with async_session_factory() as db:
        row = await db.scalar(select(User).where(User.username == username))
        assert row is not None
        row.role = UserRole.admin
        db.add(row)
        await db.commit()


async def _create_admin_headers(client, async_session_factory):
    _token, _headers, _user, username, _target, _material = await _prepare_learning_target(client, async_session_factory)
    await _promote_user_to_admin(async_session_factory, username)
    login_response = await client.post(
        "/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert api_ok(login_response), login_response.text
    token = login_response.json()["data"]["token"]["access_token"]
    return auth_headers(token)


async def _prepare_export_context(client, async_session_factory):
    _token, headers, user, _username, target, material = await _prepare_learning_target(client, async_session_factory)
    graph_response = await client.post(
        "/knowledge-graphs/generate",
        json={
            "target_id": target["id"],
            "material_id": None,
            "force_regenerate": False,
            "max_points": 8,
        },
        headers=headers,
    )
    assert api_ok(graph_response), graph_response.text

    question_response = await client.post(
        "/questions/generate",
        json={
            "material_id": material["id"],
            "target_id": target["id"],
            "question_types": ["single_choice"],
            "difficulty": "easy",
            "count": 2,
        },
        headers=headers,
    )
    assert api_ok(question_response), question_response.text
    questions = question_response.json()["data"]["questions"]
    submit_response = await client.post(
        "/tests/submit",
        json={
            "material_id": material["id"],
            "target_id": target["id"],
            "answers": [
                {"question_id": int(question["id"]), "answer": ["__wrong__"]}
                for question in questions
            ],
        },
        headers=headers,
    )
    assert api_ok(submit_response), submit_response.text

    plan_response = await client.post(
        "/review-plans/generate",
        json={
            "target_id": target["id"],
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert api_ok(plan_response), plan_response.text
    plan_id = int(plan_response.json()["data"]["id"])
    return headers, user, target, material, plan_id


@pytest.mark.asyncio
async def test_db_c25_concurrent_ai_usage_logging_records_calls(client, async_session_factory):
    concurrency = env_int("DB_C25_CONCURRENCY", 60)
    _token, headers, user, _username, target, material = await _prepare_learning_target(client, async_session_factory)
    actions = ["qa", "questions", "knowledge", "graph", "qa", "questions"]

    async with async_session_factory() as db:
        before_count = await db.scalar(
            select(func.count()).select_from(AiCallLog).where(AiCallLog.user_id == user["id"])
        )

    async def ai_call(index: int):
        action = actions[index]
        if action == "qa":
            return await client.post(
                "/qa/ask",
                json={"material_id": material["id"], "question": f"What is admin usage case {index}?"},
                headers=headers,
            )
        if action == "questions":
            return await client.post(
                "/questions/generate",
                json={
                    "material_id": material["id"],
                    "question_types": ["single_choice"],
                    "difficulty": "easy",
                    "count": 2,
                },
                headers=headers,
            )
        if action == "knowledge":
            return await client.post(
                "/knowledge/extract",
                json={"material_id": material["id"]},
                headers=headers,
            )
        return await client.post(
            "/knowledge-graphs/generate",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": False,
                "max_points": 8,
            },
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C25",
        module="ai usage logging and summary",
        code_paths=[
            "app/routers/ai_usage.py",
            "app/services/ai_usage_service.py",
            "app/repositories/ai_call_log_repository.py",
            "app/models/ai_call_log.py",
            "app/services/qa_service.py",
            "app/services/question_service.py",
            "app/services/knowledge_service.py",
            "app/services/knowledge_graph_service.py",
        ],
        concurrency=concurrency,
        operation=ai_call,
        is_success=api_ok,
        notes="Concurrent AI-powered endpoints should append ai_call_logs and remain visible in usage summary.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        after_count = await db.scalar(
            select(func.count()).select_from(AiCallLog).where(AiCallLog.user_id == user["id"])
        )

    summary_response = await client.get("/ai-usage/summary", headers=headers)
    assert api_ok(summary_response), summary_response.text
    summary = summary_response.json()["data"]
    assert after_count >= before_count
    assert summary["total_calls"] == after_count
    assert summary["prompt_tokens"] >= 0
    assert summary["completion_tokens"] >= 0
    assert summary["total_tokens"] >= 0


@pytest.mark.asyncio
async def test_db_c26_admin_list_queries_stay_up_under_write_load(client, async_session_factory):
    writer_count = env_int("DB_C26_WRITERS", 60)
    reader_count = env_int("DB_C26_READERS", 160)
    concurrency = writer_count + reader_count
    admin_headers = await _create_admin_headers(client, async_session_factory)
    endpoints = ["/admin/users", "/admin/materials", "/admin/tasks", "/admin/logs"]

    async def mixed_operation(index: int):
        if index < writer_count:
            _token, headers, _user, _username, target, _material = await _prepare_learning_target(client, async_session_factory)
            return await client.post(
                "/materials",
                data={"target_id": str(target["id"]), "auto_parse": "false"},
                files={
                    "file": (
                        f"{unique_name('admin_write')}.txt",
                        b"admin concurrent write",
                        "text/plain",
                    )
                },
                headers=headers,
            )
        endpoint = endpoints[(index - writer_count) % len(endpoints)]
        return await client.get(endpoint, headers=admin_headers)

    report, responses = await run_concurrently(
        case_id="DB-C26",
        module="admin pagination queries under write load",
        code_paths=[
            "app/routers/admin.py",
            "app/repositories/user_repository.py",
            "app/repositories/material_repository.py",
            "app/repositories/parse_task_repository.py",
            "app/repositories/admin_log_repository.py",
            "app/models/user.py",
            "app/models/material.py",
            "app/models/parse_task.py",
            "app/models/admin_log.py",
        ],
        concurrency=concurrency,
        operation=mixed_operation,
        is_success=no_server_error,
        notes=f"{reader_count} admin list queries run while {writer_count} material uploads mutate the dataset.",
    )

    assert report.success_count == concurrency
    read_responses = [
        response
        for response in responses[writer_count:]
        if not isinstance(response, Exception) and getattr(response, "status_code", 500) == 200
    ]
    assert read_responses
    assert all("total" in response.json()["data"] for response in read_responses)


@pytest.mark.asyncio
async def test_db_c27_exports_remain_available_during_background_writes(client, async_session_factory):
    headers, _user, target, material, plan_id = await _prepare_export_context(client, async_session_factory)
    exports = [
        "/exports/wrong-questions.md",
        f"/exports/review-plan/{plan_id}.md",
        f"/exports/knowledge-summary/{target['id']}.md",
        f"/exports/anki/{target['id']}.csv",
    ]
    concurrency = len(exports) + 3

    async def export_or_write(index: int):
        if index < 3:
            return await client.post(
                "/qa/ask",
                json={"material_id": material["id"], "question": f"background export write {index}"},
                headers=headers,
            )
        return await client.get(exports[index - 3], headers=headers)

    report, responses = await run_concurrently(
        case_id="DB-C27",
        module="export endpoints under concurrent writes",
        code_paths=[
            "app/routers/exports.py",
            "app/services/export_service.py",
            "app/repositories/wrong_question_repository.py",
            "app/repositories/review_plan_repository.py",
            "app/repositories/question_repository.py",
            "app/repositories/knowledge_repository.py",
            "app/repositories/knowledge_graph_repository.py",
        ],
        concurrency=concurrency,
        operation=export_or_write,
        is_success=no_server_error,
        notes="Markdown and CSV exports should avoid 5xx responses while other requests keep writing user activity.",
    )

    assert report.success_count == concurrency
    export_responses = responses[3:]
    for response in export_responses:
        assert not isinstance(response, Exception)
        assert response.status_code == 200
        assert response.text.strip()
        assert "Content-Disposition" in response.headers


@pytest.mark.asyncio
async def test_db_c28_health_checks_stay_responsive_under_load(client, async_session_factory):
    writer_count = env_int("DB_C28_WRITERS", 40)
    health_count = env_int("DB_C28_HEALTH_PROBES", 100)
    concurrency = writer_count + health_count
    admin_headers = await _create_admin_headers(client, async_session_factory)
    _token, user_headers, _user, _username, _target, material = await _prepare_learning_target(client, async_session_factory)

    async def load_or_probe(index: int):
        if index < writer_count:
            return await client.post(
                "/qa/ask",
                json={"material_id": material["id"], "question": f"health load {index}"},
                headers=user_headers,
            )
        if (index - writer_count) % 2 == 0:
            return await client.get("/health")
        return await client.get("/health/db", headers=admin_headers)

    report, _responses = await run_concurrently(
        case_id="DB-C28",
        module="health and db health probes during mixed load",
        code_paths=[
            "app/routers/health.py",
            "app/db/session.py",
            "app/services/qa_service.py",
            "app/models/ai_call_log.py",
        ],
        concurrency=concurrency,
        operation=load_or_probe,
        is_success=no_server_error,
        notes=f"{health_count} health probes run while {writer_count} background QA writes keep the application busy.",
    )

    assert report.success_count == concurrency
