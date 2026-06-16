from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.material import Material, MaterialParseStatus
from app.models.material_structure import MaterialChunk, MaterialChunkType, MaterialSection
from app.models.parse_task import ParseTask
from app.repositories.material_structure_repository import MaterialStructureRepository
from app.repositories.parse_task_repository import ParseTaskRepository
from app.services.task_queue_service import TaskQueueService
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


def _disable_parse_queue(monkeypatch) -> None:
    monkeypatch.setattr(
        TaskQueueService,
        "enqueue_parse_task",
        staticmethod(lambda task_id: f"test-parse-task-{task_id}"),
    )


async def _mark_material_parsed(async_session_factory, material_id: int) -> None:
    async with async_session_factory() as db:
        material = await db.scalar(select(Material).where(Material.id == material_id))
        assert material is not None
        material.parse_status = MaterialParseStatus.parsed
        material.parsed_text = (
            "# Transactions\n"
            "Database concurrency needs locks, isolation levels, indexes, and retry policies.\n"
            "Structured chunks should remain internally consistent during replacement.\n"
        )
        material.parse_error = None
        db.add(material)
        await db.commit()


async def _replace_structure(async_session_factory, material_id: int, index: int) -> str:
    async with async_session_factory() as db:
        section = MaterialSection(
            material_id=material_id,
            title=f"writer-section-{index}",
            level=1,
            order_index=1,
        )
        chunk = MaterialChunk(
            material_id=material_id,
            section=section,
            chunk_type=MaterialChunkType.text,
            title=f"writer-section-{index}",
            text=f"writer chunk {index}",
            order_index=1,
        )
        await MaterialStructureRepository.replace_for_material(
            db,
            material_id=material_id,
            sections=[section],
            chunks=[chunk],
        )
    return "write-ok"


async def _assert_structure_complete(async_session_factory, material_id: int) -> None:
    async with async_session_factory() as db:
        sections = await MaterialStructureRepository.list_sections_by_material(db, material_id=material_id)
        chunks = await MaterialStructureRepository.list_chunks_by_material(db, material_id=material_id)
    assert len(sections) == 1
    assert len(chunks) == 1
    assert chunks[0].section_id in {section.id for section in sections}


@pytest.mark.asyncio
async def test_db_c06_concurrent_material_uploads_create_parse_tasks(
    client,
    async_session_factory,
    monkeypatch,
):
    _disable_parse_queue(monkeypatch)
    concurrency = env_int("DB_C06_CONCURRENCY", 100)
    token, _user, _username = await create_logged_in_user(client, prefix="material_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("upload_target"))

    async def upload(index: int):
        return await client.post(
            "/materials",
            data={"target_id": str(target["id"]), "auto_parse": "true"},
            files={
                "file": (
                    f"{unique_name('concurrent')}_{index}.txt",
                    f"# Upload {index}\nConcurrent material upload test.\n".encode("utf-8"),
                    "text/plain",
                )
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C06",
        module="material upload with parse task enqueue",
        code_paths=[
            "app/routers/materials.py",
            "app/services/material_service.py",
            "app/services/parser_service.py",
            "app/repositories/material_repository.py",
            "app/repositories/parse_task_repository.py",
            "app/models/material.py",
            "app/models/parse_task.py",
        ],
        concurrency=concurrency,
        operation=upload,
        is_success=api_ok,
        notes="Concurrent uploads use unique stored filenames and create one parse task per auto_parse request.",
    )

    assert report.success_count == concurrency
    material_ids = [
        response.json()["data"]["material"]["id"]
        for response in responses
        if not isinstance(response, Exception) and api_ok(response)
    ]
    async with async_session_factory() as db:
        material_count = await db.scalar(
            select(func.count())
            .select_from(Material)
            .where(Material.target_id == target["id"], Material.id.in_(material_ids))
        )
        task_count = await db.scalar(
            select(func.count())
            .select_from(ParseTask)
            .where(ParseTask.material_id.in_(material_ids))
        )
        stored_count = await db.scalar(
            select(func.count(func.distinct(Material.stored_filename))).where(Material.id.in_(material_ids))
        )
    assert material_count == concurrency
    assert task_count == concurrency
    assert stored_count == concurrency


@pytest.mark.asyncio
async def test_db_c07_concurrent_reparse_same_material(client, async_session_factory, monkeypatch):
    _disable_parse_queue(monkeypatch)
    concurrency = env_int("DB_C07_CONCURRENCY", 100)
    token, _user, _username = await create_logged_in_user(client, prefix="reparse_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("reparse_target"))
    material = await upload_text_material(client, headers=headers, target_id=target["id"], auto_parse=False)

    async def reparse(_index: int):
        return await client.post(f"/materials/{material['id']}/parse", headers=headers)

    report, _responses = await run_concurrently(
        case_id="DB-C07",
        module="material parse task enqueue race",
        code_paths=[
            "app/routers/materials.py",
            "app/services/parser_service.py",
            "app/repositories/material_repository.py",
            "app/repositories/parse_task_repository.py",
            "app/models/material.py",
            "app/models/parse_task.py",
        ],
        concurrency=concurrency,
        operation=reparse,
        is_success=api_ok,
        notes="Repeated parse requests for one material should create explainable tasks and keep material status legal.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        task_count = await db.scalar(
            select(func.count()).select_from(ParseTask).where(ParseTask.material_id == material["id"])
        )
        row = await db.scalar(select(Material).where(Material.id == material["id"]))
    assert task_count == concurrency
    assert row is not None
    assert row.parse_status in {
        MaterialParseStatus.parsing,
        MaterialParseStatus.parsed,
        MaterialParseStatus.failed,
        MaterialParseStatus.uploaded,
    }


@pytest.mark.asyncio
async def test_db_c08_concurrent_material_delete_and_reads(client, async_session_factory):
    concurrency = env_int("DB_C08_CONCURRENCY", 100)
    token, _user, _username = await create_logged_in_user(client, prefix="delete_material_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("delete_material_target"))
    material = await upload_text_material(client, headers=headers, target_id=target["id"], auto_parse=False)

    async def delete_or_read(index: int):
        if index == 0:
            return await client.delete(f"/materials/{material['id']}", headers=headers)
        if index % 2 == 0:
            return await client.get(f"/materials/{material['id']}/preview", headers=headers)
        return await client.get(f"/materials/{material['id']}", headers=headers)

    report, _responses = await run_concurrently(
        case_id="DB-C08",
        module="material soft delete/read race",
        code_paths=[
            "app/routers/materials.py",
            "app/services/material_service.py",
            "app/repositories/material_repository.py",
            "app/models/material.py",
        ],
        concurrency=concurrency,
        operation=delete_or_read,
        is_success=no_server_error,
        notes="DELETE racing with detail/preview reads should not produce 5xx responses.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        row = await db.scalar(select(Material).where(Material.id == material["id"]))
    assert row is not None
    assert row.is_deleted is True


@pytest.mark.asyncio
async def test_db_c09_concurrent_parse_task_status_transitions(client, async_session_factory):
    concurrency = env_int("DB_C09_CONCURRENCY", 120)
    token, _user, _username = await create_logged_in_user(client, prefix="parse_status_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("parse_status_target"))
    material = await upload_text_material(client, headers=headers, target_id=target["id"], auto_parse=False)

    async with async_session_factory() as db:
        task = await ParseTaskRepository.create(db, material_id=material["id"], user_id=material["user_id"])
        task_id = task.id

    async def transition(index: int):
        async with async_session_factory() as db:
            task = await ParseTaskRepository.get_by_id(db, task_id)
            assert task is not None
            if index % 4 == 0:
                await ParseTaskRepository.mark_running(db, task)
                return "running"
            if index % 4 == 1:
                await ParseTaskRepository.mark_succeeded(db, task)
                return "succeeded"
            if index % 4 == 2:
                await ParseTaskRepository.mark_failed(db, task, failure_reason=f"failure {index}")
                return "failed"
            await ParseTaskRepository.reset_for_retry(db, task)
            return "retry"

    report, _results = await run_concurrently(
        case_id="DB-C09",
        module="parse task status machine",
        code_paths=[
            "app/repositories/parse_task_repository.py",
            "app/models/parse_task.py",
        ],
        concurrency=concurrency,
        operation=transition,
        is_success=lambda result: isinstance(result, str),
        notes="Multiple sessions update one parse task; final row must remain in a legal lifecycle state.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        final_task = await ParseTaskRepository.get_by_id(db, task_id)
    assert final_task is not None
    assert final_task.task_status.value in {"pending", "running", "succeeded", "failed"}
    assert final_task.retry_count >= 0


@pytest.mark.asyncio
async def test_db_c10_concurrent_material_structure_replace(client, async_session_factory):
    concurrency = env_int("DB_C10_CONCURRENCY", 1000)
    token, _user, _username = await create_logged_in_user(client, prefix="structure_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("structure_target"))
    material = await upload_text_material(client, headers=headers, target_id=target["id"], auto_parse=False)
    await _mark_material_parsed(async_session_factory, material["id"])

    report, _results = await run_concurrently(
        case_id="DB-C10",
        module="material structured replace",
        code_paths=[
            "app/repositories/material_structure_repository.py",
            "app/models/material_structure.py",
        ],
        concurrency=concurrency,
        operation=lambda index: _replace_structure(async_session_factory, material["id"], index),
        is_success=lambda result: result == "write-ok",
        notes="Concurrent replace_for_material calls should leave exactly one complete structure version.",
    )

    assert report.success_count == concurrency
    await _assert_structure_complete(async_session_factory, material["id"])


@pytest.mark.asyncio
async def test_db_c11_material_structure_read_while_replace(client, async_session_factory):
    writer_count = env_int("DB_C11_WRITERS", 30)
    reader_count = env_int("DB_C11_READERS", 100)
    concurrency = writer_count + reader_count
    token, _user, _username = await create_logged_in_user(client, prefix="structure_rw_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("structure_rw_target"))
    material = await upload_text_material(client, headers=headers, target_id=target["id"], auto_parse=False)
    await _mark_material_parsed(async_session_factory, material["id"])
    await _replace_structure(async_session_factory, material["id"], 0)

    async def read_or_write(index: int):
        if index < writer_count:
            return await _replace_structure(async_session_factory, material["id"], index + 1)
        return await client.get(f"/materials/{material['id']}/structured", headers=headers)

    report, _results = await run_concurrently(
        case_id="DB-C11",
        module="material structured read/write race",
        code_paths=[
            "app/routers/materials.py",
            "app/services/material_structure_service.py",
            "app/repositories/material_structure_repository.py",
            "app/models/material_structure.py",
        ],
        concurrency=concurrency,
        operation=read_or_write,
        is_success=lambda result: result == "write-ok" or no_server_error(result),
        notes=f"{writer_count} writers replace structure while {reader_count} readers query /structured.",
    )

    assert report.success_count == concurrency
    await _assert_structure_complete(async_session_factory, material["id"])
