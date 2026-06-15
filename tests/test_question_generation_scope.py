"""Tests for target/knowledge-point aware question generation helpers."""

import pytest
from pydantic import ValidationError

from app.schemas.question import QuestionGenerateRequest
from app.services import ai_service


def test_question_generate_request_accepts_target_scope():
    payload = QuestionGenerateRequest(
        target_id=1,
        knowledge_point_ids=[3, 5],
        extra_requirement="偏向期末简答题风格",
        question_types=["single_choice", "subjective"],
        count=2,
    )

    assert payload.material_id is None
    assert payload.target_id == 1
    assert payload.knowledge_point_ids == [3, 5]
    assert payload.extra_requirement == "偏向期末简答题风格"


def test_question_generate_request_requires_source_scope():
    with pytest.raises(ValidationError):
        QuestionGenerateRequest(
            question_types=["single_choice"],
            count=1,
        )


def test_mock_question_generation_prioritizes_knowledge_points(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ai_provider", "mock")

    questions = ai_service.generate_questions(
        "进程调度包括先来先服务、短作业优先和时间片轮转。死锁需要关注互斥、占有并等待、不可剥夺和循环等待。",
        material_id=1,
        question_types=["single_choice", "subjective"],
        difficulty="medium",
        count=2,
        target_title="操作系统复习",
        extra_requirement="题目偏向概念辨析",
        knowledge_points=[
            {
                "id": 10,
                "name": "进程调度",
                "description": "CPU 调度算法与评价指标",
                "importance_weight": 0.9,
            },
            {
                "id": 11,
                "name": "死锁",
                "description": "死锁条件、预防和避免",
                "importance_weight": 0.8,
            },
        ],
    )

    assert len(questions) == 2
    assert questions[0]["knowledge_points"] == ["进程调度"]
    assert questions[1]["knowledge_points"] == ["死锁"]
