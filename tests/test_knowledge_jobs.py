import uuid

import pytest

from app.models.knowledge_job import KnowledgeJobStatus, KnowledgeJobType
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.study_target import StudyTarget
from app.models.user import User
from app.repositories.knowledge_job_repository import KnowledgeJobRepository
from app.services.knowledge_job_service import KnowledgeJobService
from app.services.task_queue_service import TaskQueueService


def _username() -> str:
    return f"job_{uuid.uuid4().hex[:10]}"


async def _register_login_create_target(client) -> tuple[str, int]:
    username = _username()
    password = "password123"
    await client.post(
        "/auth/register",
        json={"username": username, "password": password, "display_name": "Job Test"},
    )
    login = await client.post("/auth/login", json={"username": username, "password": password})
    token = login.json()["data"]["token"]["access_token"]
    target = await client.post(
        "/study-targets",
        json={"title": f"Target {username}", "subject": "Testing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, target.json()["data"]["target"]["id"]


@pytest.mark.asyncio
async def test_graph_refresh_job_api_creates_and_reads_job(client, monkeypatch):
    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_knowledge_job",
        staticmethod(lambda job_id, *, queue: f"task-{queue}-{job_id}"),
    )
    token, target_id = await _register_login_create_target(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/knowledge-jobs/graph-refresh",
        json={"target_id": target_id, "force_regenerate": True, "max_points": 12},
        headers=headers,
    )
    body = resp.json()

    assert resp.status_code == 200
    assert body["code"] == 0
    job = body["data"]
    assert job["job_type"] == "graph_refresh"
    assert job["status"] == "pending"
    assert job["target_id"] == target_id

    detail = await client.get(f"/knowledge-jobs/{job['id']}", headers=headers)
    assert detail.json()["data"]["id"] == job["id"]


@pytest.mark.asyncio
async def test_knowledge_job_api_rejects_cross_user_target(client, monkeypatch):
    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_knowledge_job",
        staticmethod(lambda job_id, *, queue: f"task-{queue}-{job_id}"),
    )
    token_a, target_id = await _register_login_create_target(client)
    token_b, _ = await _register_login_create_target(client)

    resp = await client.post(
        "/knowledge-jobs/graph-refresh",
        json={"target_id": target_id, "force_regenerate": True, "max_points": 12},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resp.status_code == 200
    assert resp.json()["code"] != 0
    assert token_a != token_b


@pytest.mark.asyncio
async def test_target_graph_job_dedupes_pending_and_marks_running_rerun(
    async_session_factory,
    monkeypatch,
):
    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_knowledge_job",
        staticmethod(lambda job_id, *, queue: f"task-{queue}-{job_id}"),
    )

    async with async_session_factory() as db:
        user = User(username=_username(), hashed_password="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        target = StudyTarget(user_id=user.id, title="Async Jobs", subject="Testing")
        db.add(target)
        await db.commit()
        await db.refresh(target)

        first = await KnowledgeJobService.enqueue_graph_refresh(
            db,
            current_user=user,
            target_id=target.id,
            material_id=None,
            force_regenerate=True,
            max_points=12,
        )
        second = await KnowledgeJobService.enqueue_graph_refresh(
            db,
            current_user=user,
            target_id=target.id,
            material_id=None,
            force_regenerate=True,
            max_points=12,
        )

        assert first.id == second.id
        assert second.status == KnowledgeJobStatus.pending

        second.status = KnowledgeJobStatus.running
        db.add(second)
        await db.commit()
        running = await KnowledgeJobService.enqueue_graph_refresh(
            db,
            current_user=user,
            target_id=target.id,
            material_id=None,
            force_regenerate=True,
            max_points=12,
        )

        assert running.id == first.id
        assert running.rerun_requested is True

        latest = await KnowledgeJobRepository.get_latest(
            db,
            user_id=user.id,
            job_type=KnowledgeJobType.graph_refresh,
            target_id=target.id,
        )
        assert latest is not None
        assert latest.id == first.id


@pytest.mark.asyncio
async def test_after_material_parsed_coalesces_target_refresh_pipeline_by_target(
    async_session_factory,
    monkeypatch,
):
    queued: list[tuple[int, str]] = []

    def fake_enqueue(job_id, *, queue):
        queued.append((job_id, queue))
        return f"task-{queue}-{job_id}"

    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_knowledge_job",
        staticmethod(fake_enqueue),
    )

    async with async_session_factory() as db:
        user = User(username=_username(), hashed_password="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        target = StudyTarget(user_id=user.id, title="Async Jobs", subject="Testing")
        db.add(target)
        await db.commit()
        await db.refresh(target)
        materials = [
            Material(
                user_id=user.id,
                target_id=target.id,
                original_filename=f"m{index}.txt",
                stored_filename=f"{uuid.uuid4().hex}.txt",
                file_path=f"/tmp/m{index}.txt",
                file_type=MaterialType.txt,
                content_type="text/plain",
                file_size=10,
                parse_status=MaterialParseStatus.parsed,
                parsed_text=f"parsed text {index}",
            )
            for index in range(2)
        ]
        db.add_all(materials)
        await db.commit()
        for material in materials:
            await db.refresh(material)

        await KnowledgeJobService.enqueue_after_material_parsed(
            db,
            current_user=user,
            material_id=materials[0].id,
        )
        await KnowledgeJobService.enqueue_after_material_parsed(
            db,
            current_user=user,
            material_id=materials[1].id,
        )

        pipeline = await KnowledgeJobRepository.get_latest(
            db,
            user_id=user.id,
            job_type=KnowledgeJobType.target_refresh_pipeline,
            target_id=target.id,
        )
        assert pipeline is not None
        assert pipeline.material_id is None
        assert pipeline.status == KnowledgeJobStatus.pending

        pipeline_jobs = [
            item for item in queued if item[0] == pipeline.id and item[1] == "ai_target"
        ]
        assert len(pipeline_jobs) == 1
