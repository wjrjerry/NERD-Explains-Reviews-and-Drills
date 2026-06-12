from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.test_record import TestSubmitRequest, TestSubmitResponse
from app.services import test_service
from app.services.llm_service import LlmServiceError
from app.services.material_access_service import get_material_for_ai
from app.utils.responses import success

router = APIRouter(prefix="/tests", tags=["tests"])


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
