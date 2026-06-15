from tests.integration_helpers import (
    assert_paginated_success,
    create_student,
    create_target,
    json_request,
    register_user,
    unique_name,
)
from tests.helpers import assert_success_response


def test_health_checks_are_available() -> None:
    status, body = json_request("GET", "/health")
    assert status == 200
    assert_success_response(body)
    assert body["data"]["status"] == "ok"

    status, body = json_request("GET", "/health/db")
    assert status == 200
    assert_success_response(body)
    assert body["data"]["db"] == "ok"

    status, body = json_request("GET", "/health/redis")
    assert status == 200
    assert_success_response(body)
    assert body["data"]["redis"] == "ok"


def test_register_login_and_current_user_flow() -> None:
    username = unique_name("it_auth")
    registered_user = register_user(username)

    status, body = json_request(
        "POST",
        "/auth/login",
        payload={"username": username, "password": "123456"},
    )
    assert status == 200
    assert_success_response(body)

    token = body["data"]["token"]["access_token"]
    logged_in_user = body["data"]["user"]
    assert logged_in_user["id"] == registered_user["id"]
    assert logged_in_user["role"] == "student"

    status, body = json_request("GET", "/users/me", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["user"]["id"] == registered_user["id"]


def test_study_target_crud_flow() -> None:
    token, _user = create_student("it_target")
    target = create_target(token, title="集成测试复习目标")

    status, body = json_request("GET", "/study-targets", token=token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["id"] == target["id"] for item in body["data"]["items"])

    status, body = json_request("GET", f"/study-targets/{target['id']}", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["target"]["title"] == "集成测试复习目标"

    status, body = json_request(
        "PATCH",
        f"/study-targets/{target['id']}",
        token=token,
        payload={"review_goal": "更新后的集成测试复习目标"},
    )
    assert status == 200
    assert_success_response(body)
    assert body["data"]["target"]["review_goal"] == "更新后的集成测试复习目标"

    status, body = json_request("DELETE", f"/study-targets/{target['id']}", token=token)
    assert status == 200
    assert_success_response(body)


def test_business_api_requires_authentication() -> None:
    status, body = json_request("GET", "/materials")
    assert status == 401
    assert body["detail"]
