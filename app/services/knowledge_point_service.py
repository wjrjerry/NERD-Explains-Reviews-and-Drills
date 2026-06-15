"""Business service for knowledge point detail APIs."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import MasteryStatus, UserKnowledgeMastery
from app.models.question import Question
from app.models.wrong_question import WrongQuestion
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.repositories.question_repository import QuestionRepository
from app.schemas.knowledge_graph import (
    KnowledgePointMasteryResponse,
    KnowledgePointMasteryUpdateRequest,
    KnowledgePointMaterialItem,
    KnowledgePointMaterialsResponse,
)
from app.schemas.question import QuestionItem, QuestionOption
from app.schemas.wrong_question import MasteryStatus as WrongQuestionMasteryStatus
from app.schemas.wrong_question import WrongQuestionResponse


def _question_to_response(
    question: Question,
    *,
    point_ids: list[int],
) -> QuestionItem:
    """Map a Question row to the public question schema."""
    return QuestionItem(
        id=question.id,
        type=question.question_type.value,
        stem=question.stem,
        options=[
            QuestionOption(
                key=str(option["key"]),
                text=str(option["text"]),
                analysis=str(option.get("analysis", "")),
            )
            for option in question.options
        ],
        correct_answer=[str(answer) for answer in question.correct_answer],
        analysis=question.analysis,
        knowledge_points=[str(point) for point in question.knowledge_points],
        knowledge_point_ids=point_ids,
        difficulty=question.difficulty.value,
    )


def _wrong_question_to_response(
    row: WrongQuestion,
    *,
    point_ids: list[int] | None = None,
) -> WrongQuestionResponse:
    """Map a WrongQuestion row to the public wrong-question schema."""
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
        knowledge_point_ids=point_ids or [],
        mastery_status=WrongQuestionMasteryStatus(row.mastery_status.value),
    )


def _mastery_to_response(row: UserKnowledgeMastery) -> KnowledgePointMasteryResponse:
    """Map a mastery row to the public response schema."""
    return KnowledgePointMasteryResponse(
        knowledge_point_id=row.knowledge_point_id,
        target_id=row.target_id,
        mastery_status=row.mastery_status,
        mastery_score=row.mastery_score,
        accuracy=row.accuracy,
        answered_count=row.answered_count,
        wrong_count=row.wrong_count,
        last_practiced_at=row.last_practiced_at,
        next_review_at=row.next_review_at,
    )


async def _ensure_point_belongs_to_user(
    db: AsyncSession,
    *,
    user_id: int,
    point_id: int,
):
    """Return the point or raise LookupError for API-friendly handling."""
    point = await KnowledgeGraphRepository.get_point_by_id(
        db,
        user_id=user_id,
        point_id=point_id,
    )
    if point is None:
        raise LookupError("Knowledge point not found.")
    return point


async def list_materials(
    db: AsyncSession,
    *,
    user_id: int,
    point_id: int,
) -> KnowledgePointMaterialsResponse:
    """List material evidence for one knowledge point."""
    await _ensure_point_belongs_to_user(db, user_id=user_id, point_id=point_id)
    rows = await KnowledgeGraphRepository.list_material_evidence_for_point(
        db,
        point_id=point_id,
    )
    return KnowledgePointMaterialsResponse(
        knowledge_point_id=point_id,
        items=[
            KnowledgePointMaterialItem(
                material_id=material.id,
                target_id=material.target_id,
                original_filename=material.original_filename,
                file_type=material.file_type.value,
                parse_status=material.parse_status.value,
                evidence_text=link.evidence_text,
                relevance_score=link.relevance_score,
            )
            for link, material in rows
        ],
    )


async def list_questions(
    db: AsyncSession,
    *,
    user_id: int,
    point_id: int,
    page: int,
    page_size: int,
) -> tuple[list[QuestionItem], int]:
    """List generated questions linked to one knowledge point."""
    await _ensure_point_belongs_to_user(db, user_id=user_id, point_id=point_id)
    questions, total = await KnowledgeGraphRepository.list_questions_for_point(
        db,
        user_id=user_id,
        point_id=point_id,
        page=page,
        page_size=page_size,
    )
    link_map = await QuestionRepository.list_knowledge_point_ids_by_question_ids(
        db,
        question_ids=[question.id for question in questions],
    )
    return [
        _question_to_response(
            question,
            point_ids=link_map.get(question.id, []),
        )
        for question in questions
    ], total


async def list_wrong_questions(
    db: AsyncSession,
    *,
    user_id: int,
    point_id: int,
    page: int,
    page_size: int,
) -> tuple[list[WrongQuestionResponse], int]:
    """List wrong questions linked to one knowledge point."""
    await _ensure_point_belongs_to_user(db, user_id=user_id, point_id=point_id)
    rows, total = await KnowledgeGraphRepository.list_wrong_questions_for_point(
        db,
        user_id=user_id,
        point_id=point_id,
        page=page,
        page_size=page_size,
    )
    return [
        _wrong_question_to_response(row, point_ids=[point_id]) for row in rows
    ], total


async def update_mastery(
    db: AsyncSession,
    *,
    user_id: int,
    point_id: int,
    payload: KnowledgePointMasteryUpdateRequest,
) -> KnowledgePointMasteryResponse:
    """Manually adjust one knowledge point's mastery status or score."""
    point = await _ensure_point_belongs_to_user(db, user_id=user_id, point_id=point_id)
    row = await KnowledgeGraphRepository.get_or_create_mastery(
        db,
        user_id=user_id,
        target_id=point.target_id,
        point_id=point_id,
    )

    if payload.mastery_status is not None:
        row.mastery_status = MasteryStatus(payload.mastery_status.value)
    if payload.mastery_score is not None:
        row.mastery_score = payload.mastery_score
    if payload.next_review_at is not None:
        row.next_review_at = payload.next_review_at

    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _mastery_to_response(row)
