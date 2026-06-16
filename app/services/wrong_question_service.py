"""Business service for wrong-question book operations."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wrong_question import MasteryStatus as ModelMasteryStatus
from app.models.wrong_question import WrongQuestion
from app.repositories.question_repository import QuestionRepository
from app.repositories.wrong_question_repository import WrongQuestionRepository
from app.schemas.question import QuestionDifficulty, QuestionOption, QuestionType
from app.schemas.test_record import TestAnswerItem
from app.schemas.wrong_question import (
    MasteryStatus,
    WrongQuestionRedoResponse,
    WrongQuestionResponse,
)


def _to_response(
    row: WrongQuestion,
    *,
    knowledge_point_ids: list[int] | None = None,
    question=None,
) -> WrongQuestionResponse:
    """Map a WrongQuestion ORM row to the public response schema."""
    return WrongQuestionResponse(
        id=row.id,
        question_id=row.question_id,
        target_id=row.target_id,
        material_id=row.material_id,
        stem=row.stem,
        user_answer=[str(answer) for answer in row.user_answer],
        correct_answer=[str(answer) for answer in row.correct_answer],
        analysis=row.analysis,
        wrong_reason=row.wrong_reason,
        knowledge_points=[str(point) for point in row.knowledge_points],
        knowledge_point_ids=knowledge_point_ids or [],
        mastery_status=MasteryStatus(row.mastery_status.value),
        review_count=row.review_count,
        last_reviewed_at=row.last_reviewed_at,
        next_review_at=row.next_review_at,
        question_type=QuestionType(question.question_type.value) if question is not None else None,
        options=[
            QuestionOption(
                key=str(option.get("key", "")),
                text=str(option.get("text", "")),
            )
            for option in (question.options if question is not None else [])
        ],
        difficulty=QuestionDifficulty(question.difficulty.value) if question is not None else None,
    )


async def _responses_from_rows(
    db: AsyncSession,
    *,
    user_id: int,
    rows: list[WrongQuestion],
) -> list[WrongQuestionResponse]:
    """Batch-load links and source questions for wrong-question responses."""
    link_map = await WrongQuestionRepository.list_knowledge_point_ids_by_wrong_question_ids(
        db,
        wrong_question_ids=[row.id for row in rows],
    )
    questions = await QuestionRepository.list_by_ids(
        db,
        user_id=user_id,
        question_ids=list({row.question_id for row in rows}),
    )
    question_map = {question.id: question for question in questions}
    return [
        _to_response(
            row,
            knowledge_point_ids=link_map.get(row.id, []),
            question=question_map.get(row.question_id),
        )
        for row in rows
    ]


def _next_review_at(status: MasteryStatus, now: datetime) -> datetime:
    """Choose a compact wrong-question spaced-review interval."""
    if status == MasteryStatus.unmastered:
        return now + timedelta(days=1)
    if status == MasteryStatus.reviewing:
        return now + timedelta(days=3)
    return now + timedelta(days=10)


def _status_from_score(*, is_correct: bool, score: float) -> MasteryStatus:
    """Convert one redo result to wrong-question mastery."""
    if is_correct or score >= 0.85:
        return MasteryStatus.mastered
    if score >= 0.5:
        return MasteryStatus.reviewing
    return MasteryStatus.unmastered


async def create_wrong_questions(
    db: AsyncSession,
    *,
    user_id: int,
    test_record_id: int,
    wrong_items: list[dict[str, object]],
) -> list[WrongQuestionResponse]:
    """Create wrong-question rows from wrong self-test answers."""
    rows = await WrongQuestionRepository.create_wrong_questions(
        db,
        user_id=user_id,
        test_record_id=test_record_id,
        wrong_items=wrong_items,
    )
    return await _responses_from_rows(db, user_id=user_id, rows=rows)


async def list_wrong_questions(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
    knowledge_point_id: int | None,
    mastery_status: MasteryStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[WrongQuestionResponse], int]:
    """Return paginated wrong questions for one user with filters."""
    rows, total = await WrongQuestionRepository.list_wrong_questions(
        db,
        user_id=user_id,
        target_id=target_id,
        material_id=material_id,
        knowledge_point_id=knowledge_point_id,
        mastery_status=(
            ModelMasteryStatus(mastery_status.value)
            if mastery_status is not None
            else None
        ),
        page=page,
        page_size=page_size,
    )
    return await _responses_from_rows(db, user_id=user_id, rows=rows), total


async def get_wrong_question(
    db: AsyncSession,
    *,
    user_id: int,
    wrong_question_id: int,
) -> WrongQuestionResponse | None:
    """Return one wrong-question detail record."""
    row = await WrongQuestionRepository.get_wrong_question_by_id(
        db,
        user_id=user_id,
        wrong_question_id=wrong_question_id,
    )
    if row is None:
        return None
    responses = await _responses_from_rows(db, user_id=user_id, rows=[row])
    return responses[0]


async def update_wrong_question_mastery(
    db: AsyncSession,
    *,
    user_id: int,
    wrong_question_id: int,
    mastery_status: MasteryStatus,
) -> WrongQuestionResponse | None:
    """Change the mastery status of a wrong question and record a review touch."""
    now = datetime.now(timezone.utc)
    row = await WrongQuestionRepository.update_mastery_status(
        db,
        user_id=user_id,
        wrong_question_id=wrong_question_id,
        mastery_status=ModelMasteryStatus(mastery_status.value),
        reviewed_at=now,
        next_review_at=_next_review_at(mastery_status, now),
        increment_review_count=True,
    )
    if row is None:
        return None
    responses = await _responses_from_rows(db, user_id=user_id, rows=[row])
    return responses[0]


async def list_review_queue(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    knowledge_point_id: int | None,
    limit: int,
) -> list[WrongQuestionResponse]:
    """Return a weighted wrong-question review queue."""
    limit = max(1, min(limit, 50))
    now = datetime.now(timezone.utc)
    unmastered_limit = max(1, round(limit * 0.7))
    reviewing_limit = max(1, round(limit * 0.2)) if limit >= 3 else 0
    mastered_limit = max(1, limit - unmastered_limit - reviewing_limit) if limit >= 5 else 0

    selected: list[WrongQuestion] = []
    selected_ids: set[int] = set()

    async def extend(status: ModelMasteryStatus, count: int, *, due_only: bool) -> None:
        if count <= 0:
            return
        rows = await WrongQuestionRepository.list_review_candidates(
            db,
            user_id=user_id,
            mastery_status=status,
            target_id=target_id,
            knowledge_point_id=knowledge_point_id,
            due_at=now,
            due_only=due_only,
            exclude_ids=selected_ids,
            limit=count,
        )
        selected.extend(rows)
        selected_ids.update(row.id for row in rows)

    await extend(ModelMasteryStatus.unmastered, unmastered_limit, due_only=True)
    await extend(ModelMasteryStatus.reviewing, reviewing_limit, due_only=True)
    await extend(ModelMasteryStatus.mastered, mastered_limit, due_only=False)

    remaining = limit - len(selected)
    for status in (
        ModelMasteryStatus.unmastered,
        ModelMasteryStatus.reviewing,
        ModelMasteryStatus.mastered,
    ):
        if remaining <= 0:
            break
        await extend(status, remaining, due_only=False)
        remaining = limit - len(selected)

    return await _responses_from_rows(db, user_id=user_id, rows=selected[:limit])


async def redo_wrong_question(
    db: AsyncSession,
    *,
    user_id: int,
    wrong_question_id: int,
    answer: TestAnswerItem,
) -> WrongQuestionRedoResponse | None:
    """Re-score a wrong question and update its review state."""
    wrong = await WrongQuestionRepository.get_wrong_question_by_id(
        db,
        user_id=user_id,
        wrong_question_id=wrong_question_id,
    )
    if wrong is None:
        return None

    question = await QuestionRepository.get_question_by_id(
        db,
        user_id=user_id,
        question_id=wrong.question_id,
    )
    if question is None:
        return None

    link_map = await WrongQuestionRepository.list_knowledge_point_ids_by_wrong_question_ids(
        db,
        wrong_question_ids=[wrong.id],
    )
    point_ids = link_map.get(wrong.id, [])

    from app.services import knowledge_mastery_service, test_service
    from app.services.knowledge_mastery_service import KnowledgeMasteryAnswerOutcome

    result, _wrong_reason = await test_service.score_single_answer(
        db,
        user_id=user_id,
        question=question,
        submitted=answer,
        target_id=wrong.target_id,
        material_id=wrong.material_id,
        knowledge_point_ids=point_ids,
    )
    next_status = _status_from_score(is_correct=result.is_correct, score=result.score)
    now = datetime.now(timezone.utc)
    updated = await WrongQuestionRepository.update_mastery_status(
        db,
        user_id=user_id,
        wrong_question_id=wrong.id,
        mastery_status=ModelMasteryStatus(next_status.value),
        reviewed_at=now,
        next_review_at=_next_review_at(next_status, now),
        increment_review_count=True,
    )
    if updated is None:
        return None

    if updated.target_id is not None and point_ids:
        await knowledge_mastery_service.update_mastery_after_test(
            db,
            user_id=user_id,
            outcomes=[
                KnowledgeMasteryAnswerOutcome(
                    target_id=updated.target_id,
                    knowledge_point_ids=point_ids,
                    is_correct=result.is_correct,
                    score=result.score,
                )
            ],
        )

    responses = await _responses_from_rows(db, user_id=user_id, rows=[updated])
    return WrongQuestionRedoResponse(result=result, wrong_question=responses[0])
