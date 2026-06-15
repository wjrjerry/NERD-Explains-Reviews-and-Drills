"""Routes for the unified AI knowledge extraction module."""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeExtractRequest,
    KnowledgeExtractionScope,
    KnowledgeExtractResponse,
)
from app.schemas.response import ApiResponse
from app.services import knowledge_service
from app.utils.responses import fail, success

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/latest", response_model=ApiResponse[KnowledgeExtractResponse])
async def get_latest_knowledge(
    scope: KnowledgeExtractionScope = Query(..., description="提炼范围：material 或 target"),
    target_id: int | None = Query(default=None, description="目标级提炼所属目标 ID"),
    material_id: int | None = Query(default=None, description="资料级提炼所属资料 ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read the newest stored extraction without starting a new AI call."""
    try:
        result = await knowledge_service.get_latest_knowledge(
            db,
            current_user=current_user,
            scope=scope,
            target_id=target_id,
            material_id=material_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return success(result)


@router.post("/extract", response_model=ApiResponse[KnowledgeExtractResponse])
async def extract_knowledge(
    payload_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run material-level or target-level knowledge extraction.

    - material_id: extract a summary for one parsed material.
    - target_id: extract an aggregated target summary and refresh the graph.
    """
    if payload_data.get("material_id") is not None and payload_data.get("target_id") is not None:
        payload_data = {**payload_data, "target_id": None}

    try:
        payload = KnowledgeExtractRequest.model_validate(payload_data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    try:
        result = await knowledge_service.extract_knowledge(
            db,
            payload,
            current_user=current_user,
        )
    except ValueError as exc:
        if str(exc) == "资料未解析完成":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Material is not parsed yet.",
            ) from exc
        return fail(code=40004, message=str(exc))

    return success(result)
