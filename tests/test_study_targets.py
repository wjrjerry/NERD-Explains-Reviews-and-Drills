import uuid

import pytest


def _random_username() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_create_and_get_study_target(client):
    username = _random_username()
    password = "password123"

    # register
    await client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )

    # login
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    token = resp.json()["data"]["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create study target
    payload = {"title": "期末复习", "subject": "数学"}
    resp2 = await client.post("/study-targets", json=payload, headers=headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["code"] == 0
    target = data["data"]["target"]
    assert target["title"] == "期末复习"

    # list targets
    resp3 = await client.get("/study-targets", headers=headers)
    assert resp3.status_code == 200
    list_body = resp3.json()
    assert list_body["code"] == 0
    assert list_body["data"]["total"] >= 1
