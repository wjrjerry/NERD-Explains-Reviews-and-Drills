"""Schema tests for knowledge-point aware review plans."""

from datetime import date

from app.schemas.review_plan import ReviewPlanTask


def test_review_plan_task_can_reference_knowledge_point():
    task = ReviewPlanTask(
        id=1,
        date=date(2026, 6, 15),
        title="复习进程调度",
        content="回看资料片段并完成对应错题。",
        material_id=2,
        wrong_question_id=3,
        knowledge_point_id=4,
        completed=False,
    )

    assert task.knowledge_point_id == 4
