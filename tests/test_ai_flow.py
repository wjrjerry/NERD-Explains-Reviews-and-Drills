import asyncio
import uuid

import pytest


def _random_username() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_end_to_end_qa_flow(client):
    username = _random_username()
    password = "password123"

    # register and login
    await client.post("/auth/register", json={"username": username, "password": password})
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    token = resp.json()["data"]["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create target
    resp_target = await client.post("/study-targets", json={"title": "E2E"}, headers=headers)
    target_id = resp_target.json()["data"]["target"]["id"]

    # upload txt
    files = {
        "file": (
            "doc.txt",
            "第一章 知识点\n\n这是用于QA的示例文本：关键点 A、关键点 B。".encode("utf-8"),
            "text/plain",
        )
    }
    data = {"target_id": str(target_id)}
    resp_upload = await client.post("/materials", files=files, data=data, headers=headers)
    assert resp_upload.status_code == 200
    material_id = resp_upload.json()["data"]["material"]["id"]

    # parse material (should set parsed_text)
    resp_parse = await client.post(f"/materials/{material_id}/parse", headers=headers)
    assert resp_parse.status_code == 200
    parsed = resp_parse.json()["data"]["material"]["parse_status"]
    for _ in range(20):
        if parsed == "parsed":
            break
        await asyncio.sleep(0.1)
        resp_material = await client.get(f"/materials/{material_id}", headers=headers)
        assert resp_material.status_code == 200
        parsed = resp_material.json()["data"]["material"]["parse_status"]
    assert parsed == "parsed"

    # structured material input should be generated from parsed_text for member B
    resp_sections = await client.get(f"/materials/{material_id}/sections", headers=headers)
    assert resp_sections.status_code == 200
    sections = resp_sections.json()["data"]["sections"]
    assert sections
    assert sections[0]["title"] == "第一章 知识点"

    resp_chunks = await client.get(f"/materials/{material_id}/chunks", headers=headers)
    assert resp_chunks.status_code == 200
    chunks = resp_chunks.json()["data"]["chunks"]
    assert chunks
    assert chunks[0]["text"].startswith("这是用于QA的示例文本")

    resp_target_chunks = await client.get(f"/study-targets/{target_id}/chunks", headers=headers)
    assert resp_target_chunks.status_code == 200
    assert resp_target_chunks.json()["data"]["chunks"]

    # ask QA
    qpayload = {"material_id": material_id, "question": "关键点 A 是什么？"}
    resp_qa = await client.post("/qa/ask", json=qpayload, headers=headers)
    assert resp_qa.status_code == 200
    qa_body = resp_qa.json()
    assert qa_body["code"] == 0
    assert "answer" in qa_body["data"]
