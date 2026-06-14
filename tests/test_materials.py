import uuid

import pytest


def _random_username() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_upload_and_preview_txt_material(client):
    username = _random_username()
    password = "password123"

    await client.post("/auth/register", json={"username": username, "password": password})
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    token = resp.json()["data"]["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create study target
    resp_target = await client.post("/study-targets", json={"title": "T1"}, headers=headers)
    target_id = resp_target.json()["data"]["target"]["id"]

    # upload a small txt file
    files = {"file": ("sample.txt", "这是测试文件\n第二行".encode("utf-8"), "text/plain")}
    data = {"target_id": str(target_id)}
    resp_upload = await client.post("/materials", files=files, data=data, headers=headers)
    assert resp_upload.status_code == 200
    body = resp_upload.json()
    assert body["code"] == 0
    material = body["data"]["material"]
    material_id = material["id"]

    # preview (txt should return preview text)
    resp_preview = await client.get(f"/materials/{material_id}/preview", headers=headers)
    assert resp_preview.status_code == 200
    pbody = resp_preview.json()
    assert pbody["code"] == 0
    assert "这是测试文件" in (pbody["data"]["preview_text"] or "")
