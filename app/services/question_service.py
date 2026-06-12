"""Business service for AI question generation."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.repositories.question_repository import QuestionRepository
from app.schemas.question import (
    QuestionGenerateRequest,
    QuestionGenerateResponse,
    QuestionItem,
    QuestionOption,
)
from app.services import ai_service


def _build_question_item_from_record(question: Question) -> QuestionItem:
    """Convert a persisted Question row into the public response schema."""
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
        difficulty=question.difficulty.value,
    )


async def generate_questions(
    db: AsyncSession,
    payload: QuestionGenerateRequest,
    *,
    user_id: int,
    parsed_text: str,
) -> QuestionGenerateResponse:
    """Generate questions from material text and return structured items.

    Expected final workflow:
    1. Receive QuestionGenerateRequest from the router.
    2. Load parsed material text by payload.material_id.
    3. Call ai_service.generate_questions().
    4. Persist generated questions through question_repository.
    5. Return generated questions to the frontend.

    The router is responsible for authentication and material loading. This
    service owns AI generation and question persistence.
    """
    raw_questions = ai_service.generate_questions(
        parsed_text,
        material_id=payload.material_id,
        question_types=[question_type.value for question_type in payload.question_types],
        difficulty=payload.difficulty.value,
        count=payload.count,
    )
    saved_questions = await QuestionRepository.create_questions(
        db,
        user_id=user_id,
        material_id=payload.material_id,
        questions=raw_questions,
    )

    return QuestionGenerateResponse(
        material_id=payload.material_id,
        questions=[
            _build_question_item_from_record(question) for question in saved_questions
        ],
    )
