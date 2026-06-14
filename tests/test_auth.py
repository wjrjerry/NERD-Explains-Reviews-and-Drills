import uuid

import pytest


def _random_username() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_register_and_login(client):
    username = _random_username()
    password = "password123"

    # register
    resp = await client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
            "display_name": "测试用户",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["user"]["username"] == username

    # login
    resp2 = await client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["code"] == 0
    token = body2["data"]["token"]["access_token"]
    assert token
