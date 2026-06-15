import os

import pytest

from tests.helpers import assert_success_response
from tests.integration_helpers import (
    assert_paginated_success,
    create_parsed_material,
    json_request,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_AI_ACCEPTANCE") != "1",
    reason="set RUN_REAL_AI_ACCEPTANCE=1 to run real AI acceptance tests",
)


def _assert_real_ai_environment() -> None:
    assert os.getenv("AI_PROVIDER") == "openai-compatible"
    assert os.getenv("AI_API_KEY")
    assert os.getenv("AI_BASE_URL")
    assert os.getenv("AI_MODEL")


def test_real_ai_qa_question_scoring_and_review_plan_flow() -> None:
    """Validate the real LLM provider through the HTTP learning workflow.

    This test intentionally avoids asserting exact model text. It verifies that
    real AI calls return usable structures, persist records, and keep the
    student learning flow moving end to end.
    """
    _assert_real_ai_environment()
    token, target, material = create_parsed_material()

    status, body = json_request(
        "POST",
        "/qa/ask",
        token=token,
        payload={
            "material_id": material["id"],
            "question": "请根据资料说明需求分析和系统设计的区别。",
        },
        timeout=90,
    )
    assert status == 200
    assert_success_response(body)
    qa = body["data"]
    assert qa["answer"]
    assert qa["references"]

    status, body = json_request(
        "GET",
        f"/qa/history?material_id={material['id']}",
        token=token,
        timeout=30,
    )
    assert status == 200
    assert_paginated_success(body)
    history_item = next(
        item for item in body["data"]["items"] if item["qa_record_id"] == qa["qa_record_id"]
    )
    assert history_item["ai_provider"] == "openai-compatible"
    assert history_item["ai_model"]

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
        timeout=120,
    )
    assert status == 200
    assert_success_response(body)
    questions = body["data"]["questions"]
    assert len(questions) == 2
    assert {question["type"] for question in questions} == {"single_choice", "subjective"}

    answers = []
    for question in questions:
        if question["type"] == "subjective":
            answers.append(
                {
                    "question_id": question["id"],
                    "answer_text": "我不清楚这个知识点。",
                }
            )
        else:
            wrong_answer = "A" if question["correct_answer"] != ["A"] else "B"
            answers.append({"question_id": question["id"], "answer": [wrong_answer]})

    status, body = json_request(
        "POST",
        "/tests/submit",
        token=token,
        payload={
            "material_id": material["id"],
            "target_id": target["id"],
            "answers": answers,
        },
        timeout=120,
    )
    assert status == 200
    assert_success_response(body)
    test_result = body["data"]
    assert test_result["test_record_id"]
    assert test_result["total_count"] == 2
    assert test_result["wrong_count"] >= 1
    assert all("analysis" in item for item in test_result["results"])

    status, body = json_request(
        "POST",
        "/review-plans/generate",
        token=token,
        payload={
            "target_id": target["id"],
            "start_date": "2026-06-14",
            "end_date": "2026-06-16",
        },
        timeout=120,
    )
    assert status == 200
    assert_success_response(body)
    plan = body["data"]
    assert plan["target_id"] == target["id"]
    assert plan["title"]
    assert plan["summary"]
    assert len(plan["tasks"]) == 3
    assert all(task["title"] and task["content"] for task in plan["tasks"])
