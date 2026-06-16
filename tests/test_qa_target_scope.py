"""Schema tests for target-level QA requests and responses."""

import pytest
from pydantic import ValidationError

from app.schemas.qa import QaAskRequest, QaAskResponse, QaReference


def test_qa_ask_request_accepts_target_and_knowledge_point_scope():
    payload = QaAskRequest(
        target_id=1,
        knowledge_point_id=3,
        question="进程调度为什么重要？",
    )

    assert payload.material_id is None
    assert payload.target_id == 1
    assert payload.knowledge_point_id == 3


def test_qa_ask_request_accepts_multiple_knowledge_points():
    payload = QaAskRequest(
        target_id=1,
        knowledge_point_ids=[3, 5, 8],
        question="这几个知识点之间有什么关系？",
    )

    assert payload.target_id == 1
    assert payload.knowledge_point_ids == [3, 5, 8]


def test_qa_ask_request_requires_material_or_target_scope():
    with pytest.raises(ValidationError):
        QaAskRequest(question="这段资料的重点是什么？")


def test_qa_response_can_include_knowledge_points():
    response = QaAskResponse(
        qa_record_id=1,
        material_id=2,
        target_id=3,
        question="需求分析的目标是什么？",
        answer="需求分析用于明确系统边界、用户角色、功能范围和验收标准。",
        references=[
            QaReference(
                material_id=2,
                snippet="需求分析用于明确系统边界、用户角色、功能范围和验收标准。",
            )
        ],
        knowledge_points=[
            {
                "id": 5,
                "name": "需求分析",
                "importance_weight": 0.9,
            }
        ],
        created_at="2026-06-15T00:00:00+00:00",
    )

    assert response.target_id == 3
    assert response.knowledge_points[0].name == "需求分析"
