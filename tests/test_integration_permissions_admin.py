import time

from tests.helpers import assert_success_response
from tests.integration_helpers import (
    assert_paginated_success,
    create_parsed_material,
    create_student,
    json_request,
    promote_user_to_admin,
    register_user,
    unique_name,
)


def test_cross_user_material_access_is_forbidden() -> None:
    owner_token, _target, material = create_parsed_material()
    other_token, _other_user = create_student("it_other")

    status, body = json_request("GET", f"/materials/{material['id']}", token=other_token)
    assert status == 200
    assert body["code"] != 0
    assert body["message"] == "资料不存在"

    status, body = json_request(
        "POST",
        "/qa/ask",
        token=other_token,
        payload={"material_id": material["id"], "question": "资料里讲了什么？"},
    )
    assert status == 404
    assert body["detail"] == "Material not found."

    status, body = json_request("GET", f"/materials/{material['id']}", token=owner_token)
    assert status == 200
    assert_success_response(body)


def test_admin_permissions_task_retry_and_logs_flow() -> None:
    student_token, _target, material = create_parsed_material()

    status, body = json_request("GET", "/admin/users", token=student_token)
    assert status == 403
    assert body["detail"] == "需要管理员权限"

    admin_username = unique_name("it_admin")
    register_user(admin_username, display_name="集成测试管理员")
    promote_user_to_admin(admin_username)

    status, body = json_request(
        "POST",
        "/auth/login",
        payload={"username": admin_username, "password": "123456"},
    )
    assert status == 200
    assert_success_response(body)
    admin_token = body["data"]["token"]["access_token"]
    assert body["data"]["user"]["role"] == "admin"

    status, body = json_request("GET", "/admin/users", token=admin_token)
    assert status == 200
    assert_paginated_success(body)

    status, body = json_request("GET", "/admin/materials", token=admin_token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["id"] == material["id"] for item in body["data"]["items"])

    status, body = json_request("GET", f"/admin/tasks?material_id={material['id']}", token=admin_token)
    assert status == 200
    assert_paginated_success(body)
    assert body["data"]["total"] >= 1
    task = body["data"]["items"][0]

    status, body = json_request("POST", f"/admin/tasks/{task['id']}/retry", token=admin_token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["task"]["retry_count"] >= 1

    deadline = time.time() + 20
    latest_task = None
    while time.time() < deadline:
        status, body = json_request("GET", f"/admin/tasks?material_id={material['id']}", token=admin_token)
        assert status == 200
        latest_task = body["data"]["items"][0]
        if latest_task["task_status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.3)

    assert latest_task is not None
    assert latest_task["task_status"] in {"succeeded", "failed"}

    status, body = json_request("GET", "/admin/logs?operation_type=retry_parse", token=admin_token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["target_id"] == task["id"] for item in body["data"]["items"])
