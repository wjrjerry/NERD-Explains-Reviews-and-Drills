from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.qa import QaAskRequest, QaAskResponse, QaHistoryItem
from app.schemas.response import ApiResponse, PageResult
from app.services import qa_service
from app.services.llm_service import LlmServiceError
from app.services.material_access_service import get_material_for_ai
from app.utils.responses import page_result, success

router = APIRouter(prefix="/qa", tags=["qa"])


@router.get("/history", response_model=ApiResponse[PageResult[QaHistoryItem]])
async def list_qa_history(
    material_id: int | None = Query(default=None, description="按资料 ID 筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current student's saved material-based QA records."""
    items, total = await qa_service.list_history(
        db,
        user_id=current_user.id,
        material_id=material_id,
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


@router.post("/ask", response_model=ApiResponse[QaAskResponse])
async def ask_question(
    payload: QaAskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer a student's question based on one parsed material.

    Current flow:
    1. Read current user from JWT Authorization header.
    2. Load material from the real materials table or MOCK_MATERIALS.
    3. Reject the request if the material is not parsed.
    4. Call qa_service.ask_question() to generate an answer and save a QA record.
    """
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

    try:
        result = await qa_service.ask_question(
            db,
            payload,
            user_id=current_user.id,
            parsed_text=material.parsed_text,
        )
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return success(result)
