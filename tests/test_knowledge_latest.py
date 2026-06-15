import uuid

import pytest

from app.models.knowledge import (
    KnowledgeExtraction,
    KnowledgeExtractionScope,
    KnowledgeExtractionStatus,
)


@pytest.mark.asyncio
async def test_get_latest_target_knowledge_without_starting_generation(client):
    username = f"knowledge_latest_{uuid.uuid4().hex[:8]}"
    password = "password123"
    await client.post("/auth/register", json={"username": username, "password": password})
    login = await client.post("/auth/login", json={"username": username, "password": password})
    token_data = login.json()["data"]
    headers = {"Authorization": f"Bearer {token_data['token']['access_token']}"}

    target_response = await client.post(
        "/study-targets",
        json={"title": "软件工程复习", "subject": "软件工程"},
        headers=headers,
    )
    target_id = target_response.json()["data"]["target"]["id"]

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(
            KnowledgeExtraction(
                user_id=token_data["user"]["id"],
                target_id=target_id,
                material_id=None,
                scope=KnowledgeExtractionScope.target,
                status=KnowledgeExtractionStatus.completed,
                summary="目标级摘要",
                outline=["需求分析", "系统设计"],
                keywords=["需求", "设计"],
                key_points=["明确系统边界"],
                exam_points=["需求与设计的区别"],
            )
        )
        await db.commit()

    response = await client.get(
        f"/knowledge/latest?scope=target&target_id={target_id}",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["scope"] == "target"
    assert payload["target_id"] == target_id
    assert payload["summary"] == "目标级摘要"


@pytest.mark.asyncio
async def test_get_latest_target_knowledge_returns_404_when_missing(client):
    username = f"knowledge_missing_{uuid.uuid4().hex[:8]}"
    password = "password123"
    await client.post("/auth/register", json={"username": username, "password": password})
    login = await client.post("/auth/login", json={"username": username, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['data']['token']['access_token']}"}
    target_response = await client.post(
        "/study-targets",
        json={"title": "空目标"},
        headers=headers,
    )
    target_id = target_response.json()["data"]["target"]["id"]

    response = await client.get(
        f"/knowledge/latest?scope=target&target_id={target_id}",
        headers=headers,
    )

    assert response.status_code == 404
