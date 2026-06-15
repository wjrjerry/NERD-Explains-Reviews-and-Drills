from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.material_structure import MaterialChunkResponse, TargetChunksResponse
from app.schemas.response import ApiResponse, PageResult
from app.schemas.study_target import (
    StudyTargetCreateRequest,
    StudyTargetDetailResponse,
    StudyTargetResponse,
    StudyTargetUpdateRequest,
)
from app.services.study_target_service import StudyTargetService
from app.services.material_structure_service import MaterialStructureService
from app.utils.responses import fail, page_result, success

router = APIRouter(prefix="/study-targets", tags=["study-targets"])


@router.post("", response_model=ApiResponse[StudyTargetDetailResponse])
async def create_study_target(
    payload: StudyTargetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建课程/考试目标接口。

    目标归属用户由 JWT 鉴权结果决定，前端无需也不能传入 user_id。
    """
    target = await StudyTargetService.create(
        db,
        current_user=current_user,
        payload=payload,
    )

    return success(
        data=StudyTargetDetailResponse(
            target=StudyTargetResponse.model_validate(target),
        )
    )


@router.get("", response_model=ApiResponse[PageResult[StudyTargetResponse]])
async def list_study_targets(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """课程/考试目标列表接口。

    仅返回当前登录用户未删除的目标，并使用统一分页结构。
    """
    targets, total = await StudyTargetService.list_by_current_user(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )

    return success(
        data=page_result(
            items=[StudyTargetResponse.model_validate(target) for target in targets],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{target_id}", response_model=ApiResponse[StudyTargetDetailResponse])
async def get_study_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """课程/考试目标详情接口。

    查询时同时校验目标归属，防止用户访问他人的目标。
    """
    try:
        target = await StudyTargetService.get_detail(
            db,
            current_user=current_user,
            target_id=target_id,
        )
    except ValueError as exc:
        return fail(code=40401, message=str(exc))

    return success(
        data=StudyTargetDetailResponse(
            target=StudyTargetResponse.model_validate(target),
        )
    )


@router.get("/{target_id}/chunks", response_model=ApiResponse[TargetChunksResponse])
async def list_target_chunks(
    target_id: int,
    limit: int = Query(default=200, ge=1, le=1000, description="最多返回 chunks 数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询某个学习目标下所有资料的 chunks，供目标级知识提炼和知识图谱使用。"""
    try:
        chunks = await MaterialStructureService.list_target_chunks(
            db,
            current_user=current_user,
            target_id=target_id,
            limit=limit,
        )
    except ValueError as exc:
        return fail(code=40401, message=str(exc))

    return success(
        data=TargetChunksResponse(
            target_id=target_id,
            chunks=[MaterialChunkResponse.model_validate(chunk) for chunk in chunks],
        )
    )


@router.patch("/{target_id}", response_model=ApiResponse[StudyTargetDetailResponse])
async def update_study_target(
    target_id: int,
    payload: StudyTargetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """课程/考试目标修改接口。

    支持局部更新，未传入的字段保持原值。
    """
    try:
        target = await StudyTargetService.update(
            db,
            current_user=current_user,
            target_id=target_id,
            payload=payload,
        )
    except ValueError as exc:
        return fail(code=40401, message=str(exc))

    return success(
        data=StudyTargetDetailResponse(
            target=StudyTargetResponse.model_validate(target),
        )
    )


@router.delete("/{target_id}", response_model=ApiResponse[StudyTargetDetailResponse])
async def delete_study_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """课程/考试目标删除接口。

    当前阶段采用软删除，保留历史数据归属关系。
    """
    try:
        target = await StudyTargetService.delete(
            db,
            current_user=current_user,
            target_id=target_id,
        )
    except ValueError as exc:
        return fail(code=40401, message=str(exc))

    return success(
        data=StudyTargetDetailResponse(
            target=StudyTargetResponse.model_validate(target),
        )
    )
