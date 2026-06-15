from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.test_record_repository import TestRecordRepository
from app.schemas.response import ApiResponse, PageResult
from app.schemas.test_record import TestRecordResponse, TestSubmitRequest, TestSubmitResponse
from app.services import test_service
from app.services.llm_service import LlmServiceError
from app.services.material_access_service import get_material_for_ai
from app.utils.responses import page_result, success

router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("/records", response_model=ApiResponse[PageResult[TestRecordResponse]])
async def list_test_records(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    target_id: int | None = Query(default=None, description="按课程/考试目标筛选"),
    material_id: int | None = Query(default=None, description="按资料筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's submitted self-test records."""
    items, total = await TestRecordRepository.list_test_records(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        target_id=target_id,
        material_id=material_id,
    )
    return success(
        page_result(
            items=[TestRecordResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/submit", response_model=ApiResponse[TestSubmitResponse])
async def submit_test(
    payload: TestSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit quiz answers, calculate score, and record wrong questions."""
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
        result = await test_service.submit_test(
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
