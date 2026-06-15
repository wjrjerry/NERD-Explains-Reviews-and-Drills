from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.question import (
    QuestionGenerateRequest,
    QuestionGenerateResponse,
    QuestionHintResponse,
)
from app.schemas.response import ApiResponse
from app.services import question_service
from app.services.llm_service import LlmServiceError
from app.services.material_access_service import get_material_for_ai
from app.utils.responses import success

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/generate", response_model=ApiResponse[QuestionGenerateResponse])
async def generate_questions(
    payload: QuestionGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate quiz questions from one parsed material.

    Current flow:
    1. Read current user from JWT Authorization header.
    2. Load material from the real materials table or MOCK_MATERIALS.
    3. Reject the request if the material is not parsed.
    4. Call question_service.generate_questions() to generate and save questions.
    """
    parsed_text: str | None = None
    if payload.material_id is not None and payload.target_id is None:
        material = await get_material_for_ai(
            db,
            user_id=current_user.id,
            material_id=payload.material_id,
        )
        if material is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material not found.",
            )

        if material.parse_status != "parsed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Material is not parsed yet.",
            )
        parsed_text = material.parsed_text

    try:
        result = await question_service.generate_questions(
            db,
            payload,
            user_id=current_user.id,
            parsed_text=parsed_text,
        )
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return success(result)


@router.get(
    "/{question_id}/hints/{level}",
    response_model=ApiResponse[QuestionHintResponse],
)
async def get_question_hint(
    question_id: int,
    level: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return one hint level for a generated question owned by the user."""
    try:
        result = await question_service.get_question_hint(
            db,
            user_id=current_user.id,
            question_id=question_id,
            level=level,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success(result)
