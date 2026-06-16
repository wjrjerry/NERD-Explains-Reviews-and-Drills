from uuid import uuid4

import pytest

from app.models.knowledge_point import KnowledgePoint, KnowledgePointSource
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.question import Question, QuestionDifficulty, QuestionType
from app.models.study_target import StudyTarget, StudyTargetType
from app.models.test_record import TestRecord
from app.models.user import User, UserRole
from app.models.wrong_question import (
    MasteryStatus,
    WrongQuestion,
    WrongQuestionKnowledgePoint,
)
from app.schemas.test_record import TestAnswerItem
from app.services import test_service, wrong_question_service


async def _seed_base(db):
    suffix = uuid4().hex
    user = User(
        username=f"wrong-review-{suffix}",
        hashed_password="x",
        role=UserRole.student,
    )
    db.add(user)
    await db.flush()

    target = StudyTarget(
        user_id=user.id,
        title="Compiler",
        target_type=StudyTargetType.course,
    )
    db.add(target)
    await db.flush()

    material = Material(
        user_id=user.id,
        target_id=target.id,
        original_filename="chapter.pdf",
        stored_filename=f"{suffix}.pdf",
        file_path=f"/tmp/{suffix}.pdf",
        file_type=MaterialType.pdf,
        content_type="application/pdf",
        file_size=100,
        parse_status=MaterialParseStatus.parsed,
        parsed_text="compiler notes",
    )
    db.add(material)
    await db.flush()

    point = KnowledgePoint(
        user_id=user.id,
        target_id=target.id,
        name="Parsing",
        importance_weight=0.95,
        level=1,
        sort_order=1,
        source=KnowledgePointSource.ai_generated,
    )
    db.add(point)
    await db.flush()
    return user, target, material, point


async def _create_wrong(db, *, user, target, material, point, status, index):
    record = TestRecord(
        user_id=user.id,
        material_id=material.id,
        target_id=target.id,
        score=0,
        accuracy=0,
        total_count=1,
        correct_count=0,
        wrong_count=1,
    )
    db.add(record)
    await db.flush()

    question = Question(
        user_id=user.id,
        material_id=material.id,
        target_id=target.id,
        question_type=QuestionType.single_choice,
        stem=f"Question {index}",
        options=[{"key": "A", "text": "Right"}, {"key": "B", "text": "Wrong"}],
        correct_answer=["A"],
        analysis="Choose A.",
        hints=[],
        knowledge_points=[point.name],
        difficulty=QuestionDifficulty.medium,
    )
    db.add(question)
    await db.flush()

    wrong = WrongQuestion(
        user_id=user.id,
        test_record_id=record.id,
        question_id=question.id,
        target_id=target.id,
        material_id=material.id,
        stem=question.stem,
        user_answer=["B"],
        correct_answer=["A"],
        analysis=question.analysis,
        wrong_reason="Selected B.",
        knowledge_points=[point.name],
        mastery_status=status,
    )
    db.add(wrong)
    await db.flush()
    db.add(
        WrongQuestionKnowledgePoint(
            wrong_question_id=wrong.id,
            knowledge_point_id=point.id,
            wrong_reason=wrong.wrong_reason,
            relevance_score=1.0,
        )
    )
    await db.commit()
    await db.refresh(wrong)
    return wrong


@pytest.mark.asyncio
async def test_review_queue_includes_weighted_status_buckets(async_session_factory):
    async with async_session_factory() as db:
        user, target, material, point = await _seed_base(db)
        for index in range(7):
            await _create_wrong(
                db,
                user=user,
                target=target,
                material=material,
                point=point,
                status=MasteryStatus.unmastered,
                index=index,
            )
        for index in range(7, 9):
            await _create_wrong(
                db,
                user=user,
                target=target,
                material=material,
                point=point,
                status=MasteryStatus.reviewing,
                index=index,
            )
        await _create_wrong(
            db,
            user=user,
            target=target,
            material=material,
            point=point,
            status=MasteryStatus.mastered,
            index=9,
        )

        queue = await wrong_question_service.list_review_queue(
            db,
            user_id=user.id,
            target_id=target.id,
            knowledge_point_id=point.id,
            limit=10,
        )

        statuses = [item.mastery_status for item in queue]
        assert statuses.count("unmastered") == 7
        assert statuses.count("reviewing") == 2
        assert statuses.count("mastered") == 1


@pytest.mark.asyncio
async def test_redo_wrong_question_updates_review_state(async_session_factory):
    async with async_session_factory() as db:
        user, target, material, point = await _seed_base(db)
        wrong = await _create_wrong(
            db,
            user=user,
            target=target,
            material=material,
            point=point,
            status=MasteryStatus.unmastered,
            index=1,
        )

        result = await wrong_question_service.redo_wrong_question(
            db,
            user_id=user.id,
            wrong_question_id=wrong.id,
            answer=TestAnswerItem(question_id=wrong.question_id, answer=["A"]),
        )

        assert result is not None
        assert result.result.is_correct is True
        assert result.wrong_question.mastery_status == "mastered"
        assert result.wrong_question.review_count == 1
        assert result.wrong_question.last_reviewed_at is not None
        assert result.wrong_question.next_review_at is not None


def test_objective_scoring_does_not_call_ai_wrong_reason(monkeypatch):
    def fail_if_called(**_kwargs):
        raise AssertionError("objective scoring should not call AI wrong reason analysis")

    monkeypatch.setattr(test_service.ai_service, "analyze_wrong_reason", fail_if_called)
    question = Question(
        id=1,
        user_id=1,
        material_id=1,
        target_id=1,
        question_type=QuestionType.true_false,
        stem="Parsing builds an AST.",
        options=[
            {"key": "true", "text": "True", "analysis": "Correct."},
            {"key": "false", "text": "False", "analysis": "This confuses parsing with code generation."},
        ],
        correct_answer=["true"],
        analysis="Parsing analyzes syntax and can produce an AST.",
        hints=[],
        knowledge_points=["Parsing"],
        difficulty=QuestionDifficulty.medium,
    )

    score, is_correct, _analysis, wrong_reason, _matched, missing, _misconceptions = (
        test_service._score_objective_answer(question, ["false"])
    )

    assert score == 0
    assert is_correct is False
    assert wrong_reason
    assert missing == ["This confuses parsing with code generation."]
