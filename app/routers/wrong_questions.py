from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.response import ApiResponse, PageResult
from app.schemas.wrong_question import (
    MasteryStatus,
    WrongQuestionMasteryUpdateRequest,
    WrongQuestionRedoRequest,
    WrongQuestionRedoResponse,
    WrongQuestionResponse,
)
from app.services import wrong_question_service
from app.utils.responses import page_result, success

router = APIRouter(prefix="/wrong-questions", tags=["wrong-questions"])


@router.get("", response_model=ApiResponse[PageResult[WrongQuestionResponse]])
async def list_wrong_questions(
    target_id: int | None = Query(default=None, description="课程/考试目标 ID"),
    material_id: int | None = Query(default=None, description="资料 ID"),
    knowledge_point_id: int | None = Query(default=None, description="知识点 ID"),
    mastery_status: MasteryStatus | None = Query(default=None, description="掌握状态"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's wrong questions with optional filters."""
    items, total = await wrong_question_service.list_wrong_questions(
        db,
        user_id=current_user.id,
        target_id=target_id,
        material_id=material_id,
        knowledge_point_id=knowledge_point_id,
        mastery_status=mastery_status,
        page=page,
        page_size=page_size,
    )
    return success(
        page_result(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/review-queue", response_model=ApiResponse[list[WrongQuestionResponse]])
async def list_wrong_question_review_queue(
    target_id: int | None = Query(default=None, description="课程/考试目标 ID"),
    knowledge_point_id: int | None = Query(default=None, description="知识点 ID"),
    limit: int = Query(default=10, ge=1, le=50, description="队列题目数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a weighted review queue for wrong questions."""
    items = await wrong_question_service.list_review_queue(
        db,
        user_id=current_user.id,
        target_id=target_id,
        knowledge_point_id=knowledge_point_id,
        limit=limit,
    )
    return success(items)


@router.get("/{wrong_question_id}", response_model=ApiResponse[WrongQuestionResponse])
async def get_wrong_question(
    wrong_question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information for one wrong question."""
    result = await wrong_question_service.get_wrong_question(
        db,
        user_id=current_user.id,
        wrong_question_id=wrong_question_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wrong question not found.",
        )
    return success(result)


@router.post("/{wrong_question_id}/redo", response_model=ApiResponse[WrongQuestionRedoResponse])
async def redo_wrong_question(
    wrong_question_id: int,
    payload: WrongQuestionRedoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a new answer for one wrong question and update review state."""
    result = await wrong_question_service.redo_wrong_question(
        db,
        user_id=current_user.id,
        wrong_question_id=wrong_question_id,
        answer=payload.answer,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wrong question not found.",
        )
    return success(result)


@router.patch("/{wrong_question_id}/mastery", response_model=ApiResponse[WrongQuestionResponse])
async def update_wrong_question_mastery(
    wrong_question_id: int,
    payload: WrongQuestionMasteryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update mastery status for one wrong question."""
    result = await wrong_question_service.update_wrong_question_mastery(
        db,
        user_id=current_user.id,
        wrong_question_id=wrong_question_id,
        mastery_status=payload.mastery_status,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wrong question not found.",
        )
    return success(result)
