from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.knowledge_job import KnowledgeJob, KnowledgeJobStatus, KnowledgeJobType
from app.models.knowledge_point import KnowledgePoint, MaterialKnowledgePoint, UserKnowledgeMastery
from app.repositories.knowledge_job_repository import KnowledgeJobRepository
from app.services.task_queue_service import TaskQueueService
from tests.concurrency_helpers import (
    api_ok,
    auth_headers,
    create_logged_in_user,
    create_study_target,
    env_int,
    run_concurrently,
    unique_name,
    upload_text_material,
)
from tests.test_db_concurrency_c06_c11 import _mark_material_parsed


def _disable_knowledge_queue(monkeypatch) -> None:
    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_knowledge_job",
        staticmethod(lambda job_id, *, queue: f"test-knowledge-job-{queue}-{job_id}"),
    )


@pytest.mark.asyncio
async def test_db_c12_concurrent_knowledge_job_dedupe(
    client,
    async_session_factory,
    monkeypatch,
):
    _disable_knowledge_queue(monkeypatch)
    concurrency = env_int("DB_C12_CONCURRENCY", 10)
    token, user, _username = await create_logged_in_user(client, prefix="job_dedupe_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("job_dedupe_target"))

    async def enqueue(_index: int):
        return await client.post(
            "/knowledge-jobs/graph-refresh",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": True,
                "max_points": 12,
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C12",
        module="knowledge job dedupe",
        code_paths=[
            "app/routers/knowledge_jobs.py",
            "app/services/knowledge_job_service.py",
            "app/repositories/knowledge_job_repository.py",
            "app/models/knowledge_job.py",
        ],
        concurrency=concurrency,
        operation=enqueue,
        is_success=api_ok,
        notes="Concurrent graph-refresh enqueue requests should collapse onto one dedupe_key row.",
    )

    assert report.success_count == concurrency
    returned_ids = {
        response.json()["data"]["id"]
        for response in responses
        if not isinstance(response, Exception) and api_ok(response)
    }
    dedupe_key = KnowledgeJobRepository.build_dedupe_key(
        user_id=user["id"],
        job_type=KnowledgeJobType.graph_refresh,
        target_id=target["id"],
        material_id=None,
    )
    async with async_session_factory() as db:
        count = await db.scalar(
            select(func.count()).select_from(KnowledgeJob).where(KnowledgeJob.dedupe_key == dedupe_key)
        )
        job = await db.scalar(select(KnowledgeJob).where(KnowledgeJob.dedupe_key == dedupe_key))
    assert count == 1
    assert job is not None
    assert returned_ids == {job.id}


@pytest.mark.asyncio
async def test_db_c13_running_knowledge_job_requests_rerun(
    client,
    async_session_factory,
    monkeypatch,
):
    _disable_knowledge_queue(monkeypatch)
    concurrency = env_int("DB_C13_CONCURRENCY", 8)
    token, _user, _username = await create_logged_in_user(client, prefix="job_rerun_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("job_rerun_target"))

    first = await client.post(
        "/knowledge-jobs/graph-refresh",
        json={
            "target_id": target["id"],
            "material_id": None,
            "force_regenerate": True,
            "max_points": 12,
        },
        headers=headers,
    )
    assert api_ok(first), first.text
    job_id = first.json()["data"]["id"]

    async with async_session_factory() as db:
        job = await KnowledgeJobRepository.get_by_id(db, job_id)
        assert job is not None
        await KnowledgeJobRepository.mark_running(db, job)

    async def enqueue_rerun(index: int):
        return await client.post(
            "/knowledge-jobs/graph-refresh",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": index % 2 == 0,
                "max_points": 12,
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C13",
        module="knowledge job running/rerun",
        code_paths=[
            "app/routers/knowledge_jobs.py",
            "app/services/knowledge_job_service.py",
            "app/repositories/knowledge_job_repository.py",
            "app/models/knowledge_job.py",
        ],
        concurrency=concurrency,
        operation=enqueue_rerun,
        is_success=api_ok,
        notes="When a deduped job is running, concurrent enqueue calls should request one rerun instead of inserting new rows.",
    )

    assert report.success_count == concurrency
    returned_ids = {
        response.json()["data"]["id"]
        for response in responses
        if not isinstance(response, Exception) and api_ok(response)
    }
    async with async_session_factory() as db:
        job = await KnowledgeJobRepository.get_by_id(db, job_id)
    assert returned_ids == {job_id}
    assert job is not None
    assert job.status == KnowledgeJobStatus.running
    assert job.rerun_requested is True


@pytest.mark.asyncio
async def test_db_c14_concurrent_knowledge_graph_generate(client, async_session_factory):
    concurrency = env_int("DB_C14_CONCURRENCY", 4)
    max_points = env_int("DB_C14_MAX_POINTS", 6)
    token, user, _username = await create_logged_in_user(client, prefix="graph_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("graph_target"))
    material = await upload_text_material(
        client,
        headers=headers,
        target_id=target["id"],
        auto_parse=False,
        text=(
            "# Database Concurrency\n"
            "Transactions coordinate concurrent readers and writers.\n"
            "Locks, indexes, isolation levels, deadlock detection, and retry logic are core knowledge points.\n"
        ),
    )
    await _mark_material_parsed(async_session_factory, material["id"])

    async def generate(_index: int):
        return await client.post(
            "/knowledge-graphs/generate",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": True,
                "max_points": max_points,
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C14",
        module="knowledge graph full generate",
        code_paths=[
            "app/routers/knowledge_graphs.py",
            "app/services/knowledge_graph_service.py",
            "app/repositories/knowledge_graph_repository.py",
            "app/models/knowledge_point.py",
        ],
        concurrency=concurrency,
        operation=generate,
        is_success=api_ok,
        notes="Concurrent force-regenerate calls should leave one complete target graph with mastery and evidence rows.",
    )

    assert report.success_count == concurrency
    response_nodes = [
        response.json()["data"]["nodes"]
        for response in responses
        if not isinstance(response, Exception) and api_ok(response)
    ]
    assert all(nodes for nodes in response_nodes)

    async with async_session_factory() as db:
        points = list(
            (
                await db.execute(
                    select(KnowledgePoint).where(
                        KnowledgePoint.user_id == user["id"],
                        KnowledgePoint.target_id == target["id"],
                    )
                )
            )
            .scalars()
            .all()
        )
        point_ids = [point.id for point in points]
        mastery_count = await db.scalar(
            select(func.count())
            .select_from(UserKnowledgeMastery)
            .where(UserKnowledgeMastery.knowledge_point_id.in_(point_ids))
        )
        evidence_count = await db.scalar(
            select(func.count())
            .select_from(MaterialKnowledgePoint)
            .where(MaterialKnowledgePoint.knowledge_point_id.in_(point_ids))
        )

    point_ids_set = {point.id for point in points}
    assert len(points) >= 1
    assert all(point.name.strip() for point in points)
    assert all(point.parent_id is None or point.parent_id in point_ids_set for point in points)
    assert all(point.parent_id != point.id for point in points)
    assert mastery_count == len(points)
    assert evidence_count >= 1
