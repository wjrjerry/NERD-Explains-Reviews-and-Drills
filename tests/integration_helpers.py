import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from urllib import error, request

import asyncpg

from tests.helpers import assert_page_result, assert_success_response


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ai_study:ai_study_pwd@localhost:5432/ai_study_db",
)
TEST_MATERIAL_DIR = Path(
    os.getenv("TEST_MATERIAL_DIR", str(Path("artifacts") / "ai-study-test-materials"))
)
TEST_MATERIAL_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MATERIAL_TEXT = (
    "需求分析用于明确系统边界、用户角色、功能范围和验收标准。\n"
    "系统设计关注架构、模块划分和接口设计。\n"
    "软件测试用于验证系统是否满足需求，常见方法包括单元测试、集成测试和验收测试。\n"
    "错题复盘可以帮助发现薄弱知识点并安排后续复习。\n"
)


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def material_file(name: str = "integration-material.txt") -> Path:
    path = TEST_MATERIAL_DIR / name
    path.write_text(DEFAULT_MATERIAL_TEXT, encoding="utf-8")
    return path


def json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    req = request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def multipart_request(
    path: str,
    *,
    token: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
    content_type: str,
    timeout: int = 60,
) -> tuple[int, dict]:
    boundary = f"----pytest-boundary-{time.time_ns()}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode()
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = request.Request(
        f"{BASE_URL}{path}",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def register_user(username: str | None = None, *, display_name: str = "集成测试用户") -> dict:
    username = username or unique_name("it_user")
    status, body = json_request(
        "POST",
        "/auth/register",
        payload={
            "username": username,
            "password": "123456",
            "display_name": display_name,
        },
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["user"]


def login_user(username: str) -> tuple[str, dict]:
    status, body = json_request(
        "POST",
        "/auth/login",
        payload={"username": username, "password": "123456"},
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["token"]["access_token"], body["data"]["user"]


def create_student(prefix: str = "it_student") -> tuple[str, dict]:
    username = unique_name(prefix)
    register_user(username)
    return login_user(username)


def create_target(token: str, *, title: str = "软件工程期末复习") -> dict:
    status, body = json_request(
        "POST",
        "/study-targets",
        token=token,
        payload={
            "title": title,
            "subject": "软件工程",
            "target_type": "exam",
            "exam_date": "2026-07-01",
            "review_goal": "掌握重点章节并完成错题复盘",
        },
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["target"]


def upload_material(
    token: str,
    target_id: int,
    *,
    auto_parse: bool = True,
    file_path: Path | None = None,
    content_type: str = "text/plain",
) -> dict:
    file_path = file_path or material_file(f"{unique_name('material')}.txt")
    fields = {"target_id": str(target_id), "auto_parse": str(auto_parse).lower()}
    status, body = multipart_request(
        "/materials",
        token=token,
        fields=fields,
        file_field="file",
        file_path=file_path,
        content_type=content_type,
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["material"]


def wait_for_material_status(
    token: str,
    material_id: int,
    expected_status: str,
    *,
    timeout_seconds: int = 20,
) -> dict:
    deadline = time.time() + timeout_seconds
    latest_material = None
    while time.time() < deadline:
        status, body = json_request("GET", f"/materials/{material_id}", token=token)
        assert status == 200
        assert_success_response(body)
        latest_material = body["data"]["material"]
        if latest_material["parse_status"] == expected_status:
            return latest_material
        time.sleep(0.3)

    raise AssertionError(
        f"material {material_id} did not reach {expected_status}: {latest_material}"
    )


def create_parsed_material() -> tuple[str, dict, dict]:
    token, _user = create_student()
    target = create_target(token)
    material = upload_material(token, target["id"])
    material = wait_for_material_status(token, material["id"], "parsed")
    return token, target, material


def assert_paginated_success(body: dict) -> None:
    assert_success_response(body)
    assert_page_result(body["data"])


def database_url_for_asyncpg() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _promote_user_to_admin(username: str) -> None:
    conn = await asyncpg.connect(database_url_for_asyncpg())
    try:
        await conn.execute("UPDATE users SET role = 'admin' WHERE username = $1", username)
    finally:
        await conn.close()


def promote_user_to_admin(username: str) -> None:
    asyncio.run(_promote_user_to_admin(username))


async def _set_material_file_path(material_id: int, file_path: str) -> None:
    conn = await asyncpg.connect(database_url_for_asyncpg())
    try:
        await conn.execute(
            "UPDATE materials SET file_path = $1 WHERE id = $2",
            file_path,
            material_id,
        )
    finally:
        await conn.close()


def set_material_file_path(material_id: int, file_path: str) -> None:
    asyncio.run(_set_material_file_path(material_id, file_path))
