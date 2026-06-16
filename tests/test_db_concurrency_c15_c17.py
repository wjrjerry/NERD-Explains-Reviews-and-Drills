from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.knowledge_point import KnowledgePoint, MaterialKnowledgePoint, UserKnowledgeMastery
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


async def _prepare_graph_context(client, async_session_factory):
    token, user, _username = await create_logged_in_user(client, prefix="graph_merge_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("graph_merge_target"))
    materials = []
    for index in range(2):
        material = await upload_text_material(
            client,
            headers=headers,
            target_id=target["id"],
            auto_parse=False,
            text=(
                f"# Material {index}\n"
                "Requirements analysis, system design, locking, indexes, and retry policies.\n"
                "Knowledge graph generation should stay readable under concurrent writes.\n"
            ),
        )
        await _mark_material_parsed(async_session_factory, material["id"])
        materials.append(material)
    return token, headers, user, target, materials


async def _generate_target_graph(client, headers: dict[str, str], target_id: int, *, force_regenerate: bool, max_points: int):
    response = await client.post(
        "/knowledge-graphs/generate",
        json={
            "target_id": target_id,
            "material_id": None,
            "force_regenerate": force_regenerate,
            "max_points": max_points,
        },
        headers=headers,
    )
    assert api_ok(response), response.text
    return response.json()["data"]


async def _get_first_point_id(client, headers: dict[str, str], target_id: int) -> int:
    graph = await _generate_target_graph(
        client,
        headers,
        target_id,
        force_regenerate=False,
        max_points=8,
    )
    nodes = graph["nodes"]
    assert nodes, graph
    return int(nodes[0]["id"])


@pytest.mark.asyncio
async def test_db_c15_concurrent_target_graph_sync_merge(client, async_session_factory):
    concurrency = env_int("DB_C15_CONCURRENCY", 60)
    _token, headers, user, target, materials = await _prepare_graph_context(client, async_session_factory)

    async def generate(index: int):
        return await client.post(
            "/knowledge-graphs/generate",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": False,
                "max_points": 10 + (index % 3),
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C15",
        module="knowledge graph target sync/merge",
        code_paths=[
            "app/routers/knowledge_graphs.py",
            "app/services/knowledge_graph_service.py",
            "app/repositories/knowledge_graph_repository.py",
            "app/models/knowledge_point.py",
        ],
        concurrency=concurrency,
        operation=generate,
        is_success=api_ok,
        notes="Concurrent incremental target graph generation should keep the graph readable and linked to uploaded materials.",
    )

    assert report.success_count == concurrency
    assert all(
        response.json()["data"]["nodes"]
        for response in responses
        if not isinstance(response, Exception) and api_ok(response)
    )

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
        evidence_rows = list(
            (
                await db.execute(
                    select(MaterialKnowledgePoint).where(
                        MaterialKnowledgePoint.knowledge_point_id.in_(point_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        mastery_count = await db.scalar(
            select(func.count())
            .select_from(UserKnowledgeMastery)
            .where(UserKnowledgeMastery.knowledge_point_id.in_(point_ids))
        )

    material_ids = {material["id"] for material in materials}
    point_ids_set = {point.id for point in points}
    assert points
    assert all(point.name.strip() for point in points)
    assert all(point.parent_id is None or point.parent_id in point_ids_set for point in points)
    assert all(point.parent_id != point.id for point in points)
    assert mastery_count == len(points)
    assert evidence_rows
    assert all(link.material_id in material_ids for link in evidence_rows)


@pytest.mark.asyncio
async def test_db_c16_concurrent_graph_regenerate_merge_stays_readable(client, async_session_factory):
    concurrency = env_int("DB_C16_CONCURRENCY", 60)
    _token, headers, user, target, _materials = await _prepare_graph_context(client, async_session_factory)
    baseline = await _generate_target_graph(
        client,
        headers,
        target["id"],
        force_regenerate=False,
        max_points=10,
    )
    assert baseline["nodes"]

    async def regenerate(index: int):
        return await client.post(
            "/knowledge-graphs/generate",
            json={
                "target_id": target["id"],
                "material_id": None,
                "force_regenerate": index % 2 == 0,
                "max_points": 6 + (index % 3),
            },
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C16",
        module="knowledge point merge via concurrent regenerate",
        code_paths=[
            "app/routers/knowledge_graphs.py",
            "app/services/knowledge_graph_service.py",
            "app/repositories/knowledge_graph_repository.py",
            "app/models/knowledge_point.py",
        ],
        concurrency=concurrency,
        operation=regenerate,
        is_success=no_server_error,
        notes="Concurrent regenerate calls should not create 5xx responses or broken parent references.",
    )

    assert report.success_count == concurrency
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
    point_ids_set = {point.id for point in points}
    assert points
    assert all(point.parent_id is None or point.parent_id in point_ids_set for point in points)
    assert all(point.parent_id != point.id for point in points)


@pytest.mark.asyncio
async def test_db_c17_concurrent_mastery_updates_keep_single_row(client, async_session_factory):
    concurrency = env_int("DB_C17_CONCURRENCY", 100)
    _token, headers, user, target, _materials = await _prepare_graph_context(client, async_session_factory)
    point_id = await _get_first_point_id(client, headers, target["id"])
    statuses = ["weak", "basic", "proficient", "weak", "basic"]

    async def update_mastery(index: int):
        return await client.patch(
            f"/knowledge-points/{point_id}/mastery",
            json={"mastery_status": statuses[index % len(statuses)]},
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C17",
        module="knowledge mastery row upsert/update",
        code_paths=[
            "app/routers/knowledge_points.py",
            "app/services/knowledge_mastery_service.py",
            "app/repositories/knowledge_graph_repository.py",
            "app/models/knowledge_point.py",
        ],
        concurrency=concurrency,
        operation=update_mastery,
        is_success=no_server_error,
        notes="Concurrent mastery updates for the same point should preserve a single mastery row and a legal mastery status.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        mastery_rows = list(
            (
                await db.execute(
                    select(UserKnowledgeMastery).where(
                        UserKnowledgeMastery.user_id == user["id"],
                        UserKnowledgeMastery.target_id == target["id"],
                        UserKnowledgeMastery.knowledge_point_id == point_id,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(mastery_rows) == 1
    assert mastery_rows[0].mastery_status.value in {"unlearned", "weak", "basic", "proficient"}
