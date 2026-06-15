from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.response import ApiResponse, PageResult
from app.schemas.review_plan import ReviewPlanGenerateRequest, ReviewPlanResponse
from app.services import review_plan_service
from app.services.llm_service import LlmServiceError
from app.utils.responses import page_result, success

router = APIRouter(prefix="/review-plans", tags=["review-plans"])


@router.post("/generate", response_model=ApiResponse[ReviewPlanResponse])
async def generate_review_plan(
    payload: ReviewPlanGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and save a review plan for one study target."""
    try:
        result = await review_plan_service.generate_review_plan(
            db,
            payload,
            user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LlmServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return success(result)


@router.get("", response_model=ApiResponse[PageResult[ReviewPlanResponse]])
async def list_review_plans(
    target_id: int | None = Query(default=None, description="课程/考试目标 ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List review plans for the current user, optionally filtered by target."""
    items, total = await review_plan_service.list_review_plans(
        db,
        user_id=current_user.id,
        target_id=target_id,
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
