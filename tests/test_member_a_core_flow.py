import asyncio
import json
import os
import time
from pathlib import Path
from urllib import error, parse, request

import asyncpg

from tests.helpers import assert_api_response, assert_page_result, assert_success_response


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ai_study:ai_study_pwd@localhost:5432/ai_study_db",
)
TEST_MATERIAL_DIR = Path(os.getenv("TEST_MATERIAL_DIR", "/tmp/ai-study-test-materials"))
TEST_MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
(TEST_MATERIAL_DIR / "test.txt").write_text("x + 1 = 3\n\nx = ?\n", encoding="utf-8")


def _json_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
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
        with request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _multipart_request(
    path: str,
    *,
    token: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
    content_type: str,
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
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _register(username: str, *, display_name: str = "测试用户") -> dict:
    status, body = _json_request(
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


def _login(username: str) -> tuple[str, dict]:
    status, body = _json_request(
        "POST",
        "/auth/login",
        payload={
            "username": username,
            "password": "123456",
        },
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["token"]["access_token"], body["data"]["user"]


def _create_target(token: str) -> dict:
    status, body = _json_request(
        "POST",
        "/study-targets",
        token=token,
        payload={
            "title": "A模块接口测试目标",
            "subject": "数据库系统",
            "target_type": "exam",
            "exam_date": "2026-07-01",
            "review_goal": "验证 A 模块核心接口",
        },
    )
    assert status == 200
    assert_success_response(body)
    return body["data"]["target"]


def _wait_for_material_status(
    token: str,
    material_id: int,
    expected_status: str,
    *,
    timeout_seconds: int = 15,
) -> dict:
    deadline = time.time() + timeout_seconds
    latest_material = None
    while time.time() < deadline:
        status, body = _json_request("GET", f"/materials/{material_id}", token=token)
        assert status == 200
        assert_success_response(body)
        latest_material = body["data"]["material"]
        if latest_material["parse_status"] == expected_status:
            return latest_material
        time.sleep(0.3)

    raise AssertionError(f"material {material_id} did not reach {expected_status}: {latest_material}")


def _database_url_for_asyncpg() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _promote_user_to_admin(username: str) -> None:
    conn = await asyncpg.connect(_database_url_for_asyncpg())
    try:
        await conn.execute("UPDATE users SET role = 'admin' WHERE username = $1", username)
    finally:
        await conn.close()


async def _set_material_file_path(material_id: int, file_path: str) -> None:
    conn = await asyncpg.connect(_database_url_for_asyncpg())
    try:
        await conn.execute(
            "UPDATE materials SET file_path = $1 WHERE id = $2",
            file_path,
            material_id,
        )
    finally:
        await conn.close()


async def _get_material_parse_fields(material_id: int) -> dict:
    conn = await asyncpg.connect(_database_url_for_asyncpg())
    try:
        row = await conn.fetchrow(
            """
            SELECT parse_status, parsed_text, parse_error
            FROM materials
            WHERE id = $1
            """,
            material_id,
        )
    finally:
        await conn.close()

    assert row is not None
    return dict(row)


def test_auth_current_user_and_study_target_crud() -> None:
    suffix = time.time_ns()
    username = f"a_core_{suffix}"
    _register(username)
    token, user = _login(username)

    status, body = _json_request("GET", "/users/me", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["user"]["id"] == user["id"]

    target = _create_target(token)

    status, body = _json_request("GET", "/study-targets", token=token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])
    assert body["data"]["total"] >= 1

    status, body = _json_request("GET", f"/study-targets/{target['id']}", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["target"]["id"] == target["id"]

    status, body = _json_request(
        "PATCH",
        f"/study-targets/{target['id']}",
        token=token,
        payload={"review_goal": "更新后的复习目标"},
    )
    assert status == 200
    assert_success_response(body)
    assert body["data"]["target"]["review_goal"] == "更新后的复习目标"

    status, body = _json_request("DELETE", f"/study-targets/{target['id']}", token=token)
    assert status == 200
    assert_success_response(body)


def test_material_upload_async_parse_preview_and_delete() -> None:
    suffix = time.time_ns()
    username = f"a_material_{suffix}"
    _register(username)
    token, _user = _login(username)
    target = _create_target(token)

    status, body = _multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=TEST_MATERIAL_DIR / "test.txt",
        content_type="text/plain",
    )
    assert status == 200
    assert_success_response(body)
    material = body["data"]["material"]
    assert material["parse_status"] == "parsing"
    assert "parsed_text" not in material

    material = _wait_for_material_status(token, material["id"], "parsed")
    assert material["parse_error"] is None
    assert "parsed_text" not in material

    parse_fields = asyncio.run(_get_material_parse_fields(material["id"]))
    assert parse_fields["parse_status"] == "parsed"
    assert "x + 1 = 3" in parse_fields["parsed_text"]
    assert parse_fields["parse_error"] is None

    status, body = _json_request("GET", f"/materials?target_id={target['id']}", token=token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])
    assert any(item["id"] == material["id"] for item in body["data"]["items"])
    assert all("parsed_text" not in item for item in body["data"]["items"])

    status, body = _json_request("GET", f"/materials/{material['id']}", token=token)
    assert status == 200
    assert_success_response(body)
    assert "parsed_text" not in body["data"]["material"]

    status, body = _json_request("GET", f"/materials/{material['id']}/preview", token=token)
    assert status == 200
    assert_success_response(body)
    assert "x + 1 = 3" in body["data"]["preview_text"]

    status, body = _json_request("POST", f"/materials/{material['id']}/parse", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["material"]["parse_status"] == "parsing"
    _wait_for_material_status(token, material["id"], "parsed")

    status, body = _json_request("DELETE", f"/materials/{material['id']}", token=token)
    assert status == 200
    assert_success_response(body)

    status, _body = _json_request("GET", f"/materials/{material['id']}", token=token)
    assert status == 200


def test_upload_rejects_unsupported_file_type() -> None:
    suffix = time.time_ns()
    username = f"a_bad_file_{suffix}"
    _register(username)
    token, _user = _login(username)
    target = _create_target(token)

    bad_file = TEST_MATERIAL_DIR / "unsupported.md"
    bad_file.write_text("# unsupported\n", encoding="utf-8")

    status, body = _multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=bad_file,
        content_type="text/markdown",
    )
    assert status == 200
    assert_api_response(body)
    assert body["code"] == 40003
    assert "仅支持上传" in body["message"]


def test_upload_rejects_oversized_file() -> None:
    suffix = time.time_ns()
    username = f"a_big_file_{suffix}"
    _register(username)
    token, _user = _login(username)
    target = _create_target(token)

    big_file = TEST_MATERIAL_DIR / f"oversized-{suffix}.txt"
    with big_file.open("wb") as file:
        file.seek(51 * 1024 * 1024)
        file.write(b"\0")

    status, body = _multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=big_file,
        content_type="text/plain",
    )
    assert status == 200
    assert_api_response(body)
    assert body["code"] == 40003
    assert "文件大小不能超过" in body["message"]


def test_material_parse_failure_is_recorded() -> None:
    suffix = time.time_ns()
    username = f"a_parse_fail_{suffix}"
    _register(username)
    token, _user = _login(username)
    target = _create_target(token)

    status, body = _multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"]), "auto_parse": "false"},
        file_field="file",
        file_path=TEST_MATERIAL_DIR / "test.txt",
        content_type="text/plain",
    )
    assert status == 200
    assert_success_response(body)
    material_id = body["data"]["material"]["id"]
    assert body["data"]["material"]["parse_status"] == "uploaded"

    asyncio.run(_set_material_file_path(material_id, f"/tmp/missing-{suffix}.txt"))

    status, body = _json_request("POST", f"/materials/{material_id}/parse", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["material"]["parse_status"] == "parsing"

    material = _wait_for_material_status(token, material_id, "failed")
    assert material["parse_error"] == "资料文件不存在"


def test_ai_routes_reject_unparsed_material() -> None:
    suffix = time.time_ns()
    username = f"a_unparsed_ai_{suffix}"
    _register(username)
    token, _user = _login(username)
    target = _create_target(token)

    status, body = _multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"]), "auto_parse": "false"},
        file_field="file",
        file_path=TEST_MATERIAL_DIR / "test.txt",
        content_type="text/plain",
    )
    assert status == 200
    assert_success_response(body)
    material = body["data"]["material"]
    assert material["parse_status"] == "uploaded"
    assert "parsed_text" not in material

    status, body = _json_request(
        "POST",
        "/knowledge/extract",
        token=token,
        payload={"material_id": material["id"], "target_id": target["id"]},
    )
    assert status == 409
    assert body["detail"] == "Material is not parsed yet."

    status, body = _json_request(
        "POST",
        "/qa/ask",
        token=token,
        payload={"material_id": material["id"], "question": "这份资料讲了什么？"},
    )
    assert status == 409
    assert body["detail"] == "Material is not parsed yet."

    status, body = _json_request(
        "POST",
        "/questions/generate",
        token=token,
        payload={
            "material_id": material["id"],
            "question_types": ["single_choice"],
            "difficulty": "easy",
            "count": 1,
        },
    )
    assert status == 409
    assert body["detail"] == "Material is not parsed yet."


def test_admin_permissions_tasks_retry_and_logs() -> None:
    suffix = time.time_ns()
    student_username = f"a_student_{suffix}"
    admin_username = f"a_admin_{suffix}"

    _register(student_username)
    student_token, _student = _login(student_username)
    target = _create_target(student_token)

    status, body = _multipart_request(
        "/materials",
        token=student_token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=TEST_MATERIAL_DIR / "test.txt",
        content_type="text/plain",
    )
    assert status == 200
    material_id = body["data"]["material"]["id"]
    _wait_for_material_status(student_token, material_id, "parsed")

    status, body = _json_request("GET", "/admin/users", token=student_token)
    assert status == 403
    assert body["detail"] == "需要管理员权限"

    _register(admin_username, display_name="管理员测试")
    asyncio.run(_promote_user_to_admin(admin_username))
    admin_token, admin_user = _login(admin_username)
    assert admin_user["role"] == "admin"

    status, body = _json_request("GET", "/admin/users", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])

    status, body = _json_request("GET", f"/admin/materials?user_id={admin_user['id']}", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])

    status, body = _json_request("GET", f"/admin/tasks?material_id={material_id}", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])
    assert body["data"]["total"] >= 1
    task = body["data"]["items"][0]

    status, body = _json_request("POST", f"/admin/tasks/{task['id']}/retry", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["task"]["retry_count"] >= 1

    deadline = time.time() + 15
    latest_task = None
    while time.time() < deadline:
        status, body = _json_request("GET", f"/admin/tasks?material_id={material_id}", token=admin_token)
        assert status == 200
        latest_task = body["data"]["items"][0]
        if latest_task["task_status"] == "succeeded":
            break
        time.sleep(0.3)
    assert latest_task["task_status"] == "succeeded"

    status, body = _json_request("GET", "/admin/logs?operation_type=retry_parse", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert_page_result(body["data"])
    assert any(item["target_id"] == task["id"] for item in body["data"]["items"])
