"""Business service for wrong-question book operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wrong_question import MasteryStatus as ModelMasteryStatus
from app.models.wrong_question import WrongQuestion
from app.repositories.wrong_question_repository import WrongQuestionRepository
from app.schemas.wrong_question import (
    MasteryStatus,
    WrongQuestionResponse,
)


def _to_response(row: WrongQuestion) -> WrongQuestionResponse:
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
        mastery_status=MasteryStatus(row.mastery_status.value),
    )


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
    return [_to_response(row) for row in rows]


async def list_wrong_questions(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
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
        mastery_status=(
            ModelMasteryStatus(mastery_status.value)
            if mastery_status is not None
            else None
        ),
        page=page,
        page_size=page_size,
    )
    return [_to_response(row) for row in rows], total


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
    return _to_response(row)


async def update_wrong_question_mastery(
    db: AsyncSession,
    *,
    user_id: int,
    wrong_question_id: int,
    mastery_status: MasteryStatus,
) -> WrongQuestionResponse | None:
    """Change the mastery status of a wrong question."""
    row = await WrongQuestionRepository.update_mastery_status(
        db,
        user_id=user_id,
        wrong_question_id=wrong_question_id,
        mastery_status=ModelMasteryStatus(mastery_status.value),
    )
    if row is None:
        return None
    return _to_response(row)
