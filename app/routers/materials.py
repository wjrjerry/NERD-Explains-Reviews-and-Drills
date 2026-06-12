from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.material import MaterialDetailResponse, MaterialPreviewResponse, MaterialResponse
from app.schemas.response import ApiResponse, PageResult
from app.services.material_service import MaterialService
from app.services.parser_service import ParserService
from app.utils.responses import fail, page_result, success

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("", response_model=ApiResponse[MaterialDetailResponse])
async def upload_material(
    target_id: int = Form(..., description="所属课程/考试目标 ID"),
    file: UploadFile = File(..., description="上传资料文件"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料上传接口。

    支持 PDF、TXT 和图片资料，并校验文件大小。
    """
    try:
        material = await MaterialService.upload(
            db,
            current_user=current_user,
            target_id=target_id,
            file=file,
        )
    except ValueError as exc:
        return fail(code=40003, message=str(exc))

    return success(
        data=MaterialDetailResponse(
            material=MaterialResponse.model_validate(material),
        )
    )


@router.get("", response_model=ApiResponse[PageResult[MaterialResponse]])
async def list_materials(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    target_id: int | None = Query(default=None, description="课程/考试目标 ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料列表接口。

    仅返回当前登录用户未删除的资料，支持按目标 ID 筛选，并使用统一分页结构。
    """
    materials, total = await MaterialService.list_by_current_user(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        target_id=target_id,
    )

    return success(
        data=page_result(
            items=[MaterialResponse.model_validate(material) for material in materials],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{material_id}", response_model=ApiResponse[MaterialDetailResponse])
async def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料详情接口。

    查询时校验资料归属，防止用户访问他人的资料。
    """
    try:
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialDetailResponse(
            material=MaterialResponse.model_validate(material),
        )
    )


@router.get("/{material_id}/preview", response_model=ApiResponse[MaterialPreviewResponse])
async def preview_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料预览接口。

    第一阶段 TXT 返回文本内容，PDF 和图片返回暂不支持文本预览的提示。
    """
    try:
        material, preview_text, message = await MaterialService.preview(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialPreviewResponse(
            material=MaterialResponse.model_validate(material),
            preview_text=preview_text,
            message=message,
        )
    )

@router.post("/{material_id}/parse", response_model=ApiResponse[MaterialDetailResponse])
async def parse_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料解析接口。

    当前执行 TXT 真实文本提取；PDF 和图片 OCR 待后续真实解析服务接入。
    """
    try:
        material = await ParserService.parse(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialDetailResponse(
            material=MaterialResponse.model_validate(material),
        )
    )

@router.delete("/{material_id}", response_model=ApiResponse[MaterialDetailResponse])
async def delete_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料删除接口。

    当前阶段采用软删除，保留文件和历史记录以便排查。
    """
    try:
        material = await MaterialService.delete(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialDetailResponse(
            material=MaterialResponse.model_validate(material),
        )
    )
