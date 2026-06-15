"""Tests for knowledge-point summaries in test submission responses."""

from app.schemas.test_record import TestResultItem as ResultItem
from app.services.test_service import _build_knowledge_point_summary


def test_build_knowledge_point_summary_aggregates_results():
    results = [
        ResultItem(
            question_id=1,
            knowledge_point_ids=[10],
            user_answer=["A"],
            correct_answer=["A"],
            is_correct=True,
            score=1.0,
            analysis="正确",
        ),
        ResultItem(
            question_id=2,
            knowledge_point_ids=[10, 11],
            user_answer=["B"],
            correct_answer=["A"],
            is_correct=False,
            score=0.0,
            analysis="错误",
        ),
    ]

    summaries = _build_knowledge_point_summary(results)
    summary_by_point = {item.knowledge_point_id: item for item in summaries}

    assert summary_by_point[10].total_count == 2
    assert summary_by_point[10].correct_count == 1
    assert summary_by_point[10].accuracy == 0.5
    assert summary_by_point[11].wrong_count == 1
