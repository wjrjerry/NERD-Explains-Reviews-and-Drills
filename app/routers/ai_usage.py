"""Routers for current user's AI token usage and local billing."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.ai_call_log import AiCallStatus
from app.models.user import User
from app.schemas.ai_usage import AiUsageLogItem, AiUsageSummary
from app.schemas.response import ApiResponse, PageResult
from app.services import ai_usage_service
from app.utils.responses import page_result, success

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("/summary", response_model=ApiResponse[AiUsageSummary])
async def get_my_ai_usage_summary(
    target_id: int | None = Query(default=None, description="按课程/考试目标筛选"),
    material_id: int | None = Query(default=None, description="按资料筛选"),
    start_at: datetime | None = Query(default=None, description="开始时间，ISO 8601"),
    end_at: datetime | None = Query(default=None, description="结束时间，ISO 8601"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return token usage and local estimated cost summary for current user."""
    summary = await ai_usage_service.summarize_usage(
        db,
        user_id=current_user.id,
        target_id=target_id,
        material_id=material_id,
        start_at=start_at,
        end_at=end_at,
    )
    return success(summary)


@router.get("/logs", response_model=ApiResponse[PageResult[AiUsageLogItem]])
async def list_my_ai_usage_logs(
    target_id: int | None = Query(default=None, description="按课程/考试目标筛选"),
    material_id: int | None = Query(default=None, description="按资料筛选"),
    feature: str | None = Query(default=None, description="按功能筛选"),
    status: AiCallStatus | None = Query(default=None, description="按调用状态筛选"),
    start_at: datetime | None = Query(default=None, description="开始时间，ISO 8601"),
    end_at: datetime | None = Query(default=None, description="结束时间，ISO 8601"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's AI provider calls and local estimated costs."""
    items, total = await ai_usage_service.list_usage_logs(
        db,
        user_id=current_user.id,
        target_id=target_id,
        material_id=material_id,
        feature=feature,
        status=status,
        start_at=start_at,
        end_at=end_at,
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
