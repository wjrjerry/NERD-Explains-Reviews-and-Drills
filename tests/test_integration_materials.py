from pathlib import Path

from tests.helpers import assert_api_response, assert_success_response
from tests.integration_helpers import (
    TEST_MATERIAL_DIR,
    assert_paginated_success,
    create_student,
    create_target,
    json_request,
    material_file,
    multipart_request,
    set_material_file_path,
    unique_name,
    upload_material,
    wait_for_material_status,
)


def test_txt_material_upload_parse_preview_reparse_and_delete() -> None:
    token, _user = create_student("it_material")
    target = create_target(token)

    material = upload_material(token, target["id"])
    assert material["parse_status"] in {"uploaded", "parsing"}

    material = wait_for_material_status(token, material["id"], "parsed")
    assert material["parse_error"] is None

    status, body = json_request("GET", f"/materials?target_id={target['id']}", token=token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["id"] == material["id"] for item in body["data"]["items"])

    status, body = json_request("GET", f"/materials/{material['id']}/preview", token=token)
    assert status == 200
    assert_success_response(body)
    assert "需求分析用于明确系统边界" in body["data"]["preview_text"]

    status, body = json_request("POST", f"/materials/{material['id']}/parse", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["material"]["parse_status"] in {"uploaded", "parsing", "parsed"}
    wait_for_material_status(token, material["id"], "parsed")

    status, body = json_request("DELETE", f"/materials/{material['id']}", token=token)
    assert status == 200
    assert_success_response(body)


def test_ai_endpoints_reject_unparsed_material() -> None:
    token, _user = create_student("it_unparsed")
    target = create_target(token)
    material = upload_material(token, target["id"], auto_parse=False)
    assert material["parse_status"] == "uploaded"

    payloads = [
        ("/qa/ask", {"material_id": material["id"], "question": "需求分析是什么？"}),
        ("/knowledge/extract", {"material_id": material["id"], "target_id": target["id"]}),
        (
            "/questions/generate",
            {
                "material_id": material["id"],
                "question_types": ["single_choice"],
                "difficulty": "easy",
                "count": 1,
            },
        ),
    ]
    for path, payload in payloads:
        status, body = json_request("POST", path, token=token, payload=payload)
        assert status == 409
        assert body["detail"] == "Material is not parsed yet."


def test_upload_rejects_unsupported_file_type() -> None:
    token, _user = create_student("it_bad_file")
    target = create_target(token)
    bad_file = TEST_MATERIAL_DIR / f"{unique_name('unsupported')}.md"
    bad_file.write_text("# unsupported\n", encoding="utf-8")

    status, body = multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=bad_file,
        content_type="text/markdown",
    )

    assert status == 200
    assert_api_response(body)
    assert body["code"] != 0
    assert "仅支持上传" in body["message"]


def test_upload_rejects_oversized_file() -> None:
    token, _user = create_student("it_big_file")
    target = create_target(token)
    big_file = TEST_MATERIAL_DIR / f"{unique_name('oversized')}.txt"
    with big_file.open("wb") as file:
        file.seek(51 * 1024 * 1024)
        file.write(b"\0")

    status, body = multipart_request(
        "/materials",
        token=token,
        fields={"target_id": str(target["id"])},
        file_field="file",
        file_path=big_file,
        content_type="text/plain",
        timeout=120,
    )

    assert status == 200
    assert_api_response(body)
    assert body["code"] != 0
    assert "文件大小不能超过" in body["message"]


def test_upload_rejects_missing_target_id() -> None:
    token, _user = create_student("it_missing_target")
    file_path = material_file(f"{unique_name('orphan')}.txt")

    status, body = multipart_request(
        "/materials",
        token=token,
        fields={"target_id": "999999999"},
        file_field="file",
        file_path=file_path,
        content_type="text/plain",
    )

    assert status == 200
    assert body["code"] != 0
    assert "目标" in body["message"] or "不存在" in body["message"]


def test_parse_failure_is_persisted() -> None:
    token, _user = create_student("it_parse_fail")
    target = create_target(token)
    material = upload_material(token, target["id"], auto_parse=False)

    missing_path = Path("/tmp") / f"missing-{unique_name('material')}.txt"
    set_material_file_path(material["id"], str(missing_path))

    status, body = json_request("POST", f"/materials/{material['id']}/parse", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["material"]["parse_status"] == "parsing"

    material = wait_for_material_status(token, material["id"], "failed")
    assert material["parse_error"] == "资料文件不存在"
