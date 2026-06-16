"""Routes for asynchronous knowledge extraction and graph refresh jobs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.knowledge_job import KnowledgeJobType
from app.models.user import User
from app.repositories.knowledge_job_repository import KnowledgeJobRepository
from app.schemas.knowledge_job import (
    GraphRefreshJobRequest,
    KnowledgeJobResponse,
    MaterialExtractJobRequest,
    TargetExtractJobRequest,
)
from app.schemas.response import ApiResponse
from app.services.knowledge_job_service import KnowledgeJobService
from app.utils.responses import fail, success

router = APIRouter(prefix="/knowledge-jobs", tags=["knowledge-jobs"])


@router.post("/material-extract", response_model=ApiResponse[KnowledgeJobResponse])
async def create_material_extract_job(
    payload: MaterialExtractJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await KnowledgeJobService.enqueue_material_extract(
            db,
            current_user=current_user,
            material_id=payload.material_id,
        )
    except ValueError as exc:
        return fail(code=40004, message=str(exc))

    return success(KnowledgeJobResponse.model_validate(job))


@router.post("/target-extract", response_model=ApiResponse[KnowledgeJobResponse])
async def create_target_extract_job(
    payload: TargetExtractJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await KnowledgeJobService.enqueue_target_extract(
            db,
            current_user=current_user,
            target_id=payload.target_id,
            force_regenerate=payload.force_regenerate,
        )
    except ValueError as exc:
        return fail(code=40004, message=str(exc))

    return success(KnowledgeJobResponse.model_validate(job))


@router.post("/graph-refresh", response_model=ApiResponse[KnowledgeJobResponse])
async def create_graph_refresh_job(
    payload: GraphRefreshJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await KnowledgeJobService.enqueue_graph_refresh(
            db,
            current_user=current_user,
            target_id=payload.target_id,
            material_id=payload.material_id,
            force_regenerate=payload.force_regenerate,
            max_points=payload.max_points,
        )
    except ValueError as exc:
        return fail(code=40004, message=str(exc))

    return success(KnowledgeJobResponse.model_validate(job))


@router.get("/latest", response_model=ApiResponse[KnowledgeJobResponse | None])
async def get_latest_job(
    target_id: int | None = Query(default=None),
    material_id: int | None = Query(default=None),
    job_type: KnowledgeJobType | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await KnowledgeJobRepository.get_latest(
        db,
        user_id=current_user.id,
        job_type=job_type,
        target_id=target_id,
        material_id=material_id,
    )
    return success(KnowledgeJobResponse.model_validate(job) if job is not None else None)


@router.get("/{job_id}", response_model=ApiResponse[KnowledgeJobResponse])
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await KnowledgeJobRepository.get_by_id(db, job_id)
    if job is None or job.user_id != current_user.id:
        return fail(code=40404, message="知识任务不存在")
    return success(KnowledgeJobResponse.model_validate(job))
