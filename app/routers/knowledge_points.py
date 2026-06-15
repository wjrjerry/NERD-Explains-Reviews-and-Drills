"""Routers for knowledge point detail and drill entry APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge_graph import (
    KnowledgePointMasteryResponse,
    KnowledgePointMasteryUpdateRequest,
    KnowledgePointMaterialsResponse,
)
from app.schemas.question import QuestionItem
from app.schemas.response import ApiResponse, PageResult
from app.schemas.wrong_question import WrongQuestionResponse
from app.services import knowledge_point_service
from app.utils.responses import page_result, success

router = APIRouter(prefix="/knowledge-points", tags=["knowledge-points"])


@router.get(
    "/{knowledge_point_id}/materials",
    response_model=ApiResponse[KnowledgePointMaterialsResponse],
)
async def list_knowledge_point_materials(
    knowledge_point_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List materials and evidence snippets supporting one knowledge point."""
    try:
        result = await knowledge_point_service.list_materials(
            db,
            user_id=current_user.id,
            point_id=knowledge_point_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success(result)


@router.get(
    "/{knowledge_point_id}/questions",
    response_model=ApiResponse[PageResult[QuestionItem]],
)
async def list_knowledge_point_questions(
    knowledge_point_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List generated questions linked to one knowledge point."""
    try:
        items, total = await knowledge_point_service.list_questions(
            db,
            user_id=current_user.id,
            point_id=knowledge_point_id,
            page=page,
            page_size=page_size,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success(
        page_result(items=items, total=total, page=page, page_size=page_size)
    )


@router.get(
    "/{knowledge_point_id}/wrong-questions",
    response_model=ApiResponse[PageResult[WrongQuestionResponse]],
)
async def list_knowledge_point_wrong_questions(
    knowledge_point_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List wrong questions linked to one knowledge point."""
    try:
        items, total = await knowledge_point_service.list_wrong_questions(
            db,
            user_id=current_user.id,
            point_id=knowledge_point_id,
            page=page,
            page_size=page_size,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success(
        page_result(items=items, total=total, page=page, page_size=page_size)
    )


@router.patch(
    "/{knowledge_point_id}/mastery",
    response_model=ApiResponse[KnowledgePointMasteryResponse],
)
async def update_knowledge_point_mastery(
    knowledge_point_id: int,
    payload: KnowledgePointMasteryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually adjust one knowledge point's mastery state."""
    try:
        result = await knowledge_point_service.update_mastery(
            db,
            user_id=current_user.id,
            point_id=knowledge_point_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success(result)
