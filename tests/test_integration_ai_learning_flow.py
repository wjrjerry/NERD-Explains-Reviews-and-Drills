from tests.helpers import assert_success_response
from tests.integration_helpers import (
    assert_paginated_success,
    create_parsed_material,
    json_request,
)


def test_knowledge_extraction_qa_and_history_flow() -> None:
    token, target, material = create_parsed_material()

    status, body = json_request(
        "POST",
        "/knowledge/extract",
        token=token,
        payload={"material_id": material["id"], "target_id": target["id"]},
    )
    assert status == 200
    assert_success_response(body)
    extraction = body["data"]
    assert extraction["material_id"] == material["id"]
    assert extraction["summary"]
    assert extraction["outline"]
    assert extraction["keywords"]
    assert extraction["key_points"]
    assert extraction["exam_points"]

    question = "需求分析和系统设计有什么区别？"
    status, body = json_request(
        "POST",
        "/qa/ask",
        token=token,
        payload={"material_id": material["id"], "question": question},
    )
    assert status == 200
    assert_success_response(body)
    qa = body["data"]
    assert qa["qa_record_id"]
    assert qa["question"] == question
    assert qa["answer"]
    assert qa["references"]
    assert qa["references"][0]["material_id"] == material["id"]

    status, body = json_request("GET", f"/qa/history?material_id={material['id']}", token=token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["qa_record_id"] == qa["qa_record_id"] for item in body["data"]["items"])


def test_question_generation_self_test_wrong_questions_and_review_plan_flow() -> None:
    token, target, material = create_parsed_material()

    status, body = json_request(
        "POST",
        "/questions/generate",
        token=token,
        payload={
            "material_id": material["id"],
            "question_types": ["single_choice", "subjective"],
            "difficulty": "medium",
            "count": 2,
        },
    )
    assert status == 200
    assert_success_response(body)
    generated = body["data"]["questions"]
    assert len(generated) == 2

    answers = []
    for question in generated:
        if question["type"] == "subjective":
            answers.append(
                {
                    "question_id": question["id"],
                    "answer_text": "我还没有掌握这个知识点。",
                }
            )
        else:
            answers.append({"question_id": question["id"], "answer": []})

    status, body = json_request(
        "POST",
        "/tests/submit",
        token=token,
        payload={
            "material_id": material["id"],
            "target_id": target["id"],
            "answers": answers,
        },
    )
    assert status == 200
    assert_success_response(body)
    result = body["data"]
    assert result["test_record_id"]
    assert result["total_count"] == len(answers)
    assert result["wrong_count"] >= 1
    assert result["results"]

    status, body = json_request(
        "GET",
        f"/wrong-questions?target_id={target['id']}&material_id={material['id']}",
        token=token,
    )
    assert status == 200
    assert_paginated_success(body)
    assert body["data"]["total"] >= 1
    wrong_question = body["data"]["items"][0]

    status, body = json_request("GET", f"/wrong-questions/{wrong_question['id']}", token=token)
    assert status == 200
    assert_success_response(body)
    assert body["data"]["id"] == wrong_question["id"]

    status, body = json_request(
        "PATCH",
        f"/wrong-questions/{wrong_question['id']}/mastery",
        token=token,
        payload={"mastery_status": "reviewing"},
    )
    assert status == 200
    assert_success_response(body)
    assert body["data"]["mastery_status"] == "reviewing"

    status, body = json_request(
        "POST",
        "/review-plans/generate",
        token=token,
        payload={
            "target_id": target["id"],
            "start_date": "2026-06-12",
            "end_date": "2026-06-14",
        },
    )
    assert status == 200
    assert_success_response(body)
    plan = body["data"]
    assert plan["target_id"] == target["id"]
    assert plan["title"]
    assert plan["summary"]
    assert len(plan["tasks"]) == 3

    status, body = json_request("GET", f"/review-plans?target_id={target['id']}", token=token)
    assert status == 200
    assert_paginated_success(body)
    assert any(item["id"] == plan["id"] for item in body["data"]["items"])


def test_submit_rejects_duplicate_question_ids() -> None:
    token, _target, material = create_parsed_material()
    status, body = json_request(
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
    assert status == 200
    question = body["data"]["questions"][0]

    status, body = json_request(
        "POST",
        "/tests/submit",
        token=token,
        payload={
            "material_id": material["id"],
            "answers": [
                {"question_id": question["id"], "answer": ["A"]},
                {"question_id": question["id"], "answer": ["B"]},
            ],
        },
    )
    assert status == 400
    assert body["detail"] == "duplicate question_id is not allowed"
