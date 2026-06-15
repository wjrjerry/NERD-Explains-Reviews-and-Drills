from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.material import MaterialDetailResponse, MaterialPreviewResponse, MaterialResponse
from app.schemas.material_structure import (
    MaterialChunksResponse,
    MaterialChunkResponse,
    MaterialFiguresResponse,
    MaterialFigureResponse,
    MaterialFormulasResponse,
    MaterialFormulaResponse,
    MaterialSectionsResponse,
    MaterialSectionResponse,
    MaterialStructuredResponse,
    MaterialTablesResponse,
    MaterialTableResponse,
)
from app.schemas.response import ApiResponse, PageResult
from app.services.material_service import MaterialService
from app.services.material_structure_service import MaterialStructureService
from app.services.parser_service import ParserService
from app.utils.responses import fail, page_result, success

router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("", response_model=ApiResponse[MaterialDetailResponse])
async def upload_material(
    background_tasks: BackgroundTasks,
    target_id: int = Form(..., description="所属课程/考试目标 ID"),
    auto_parse: bool = Form(default=True, description="上传成功后是否自动解析"),
    file: UploadFile = File(..., description="上传资料文件"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料上传接口。

    支持 PDF、TXT 和图片资料，并校验文件大小。默认上传成功后进入后台解析，
    立即返回 parsing 状态，前端可通过详情或列表接口轮询最新状态。
    """
    try:
        material = await MaterialService.upload(
            db,
            current_user=current_user,
            target_id=target_id,
            file=file,
        )
        if auto_parse:
            material, task = await ParserService.enqueue_material_parse(db, material=material)
            background_tasks.add_task(ParserService.parse_material_by_task_id, task.id)
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


@router.get("/{material_id}/sections", response_model=ApiResponse[MaterialSectionsResponse])
async def list_material_sections(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询资料章节结构。"""
    try:
        sections = await MaterialStructureService.list_sections(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialSectionsResponse(
            material_id=material_id,
            sections=[MaterialSectionResponse.model_validate(section) for section in sections],
        )
    )


@router.get("/{material_id}/chunks", response_model=ApiResponse[MaterialChunksResponse])
async def list_material_chunks(
    material_id: int,
    section_id: int | None = Query(default=None, description="按章节 ID 筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询资料文本 chunks，供知识提炼、问答、出题和知识图谱消费。"""
    try:
        chunks = await MaterialStructureService.list_chunks(
            db,
            current_user=current_user,
            material_id=material_id,
            section_id=section_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialChunksResponse(
            material_id=material_id,
            chunks=[MaterialChunkResponse.model_validate(chunk) for chunk in chunks],
        )
    )


@router.get("/{material_id}/figures", response_model=ApiResponse[MaterialFiguresResponse])
async def list_material_figures(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询资料中的图片、几何图和流程图说明。"""
    try:
        figures = await MaterialStructureService.list_figures(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialFiguresResponse(
            material_id=material_id,
            figures=[MaterialFigureResponse.model_validate(figure) for figure in figures],
        )
    )


@router.get("/{material_id}/tables", response_model=ApiResponse[MaterialTablesResponse])
async def list_material_tables(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询资料中的表格内容。"""
    try:
        tables = await MaterialStructureService.list_tables(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialTablesResponse(
            material_id=material_id,
            tables=[MaterialTableResponse.model_validate(table) for table in tables],
        )
    )


@router.get("/{material_id}/formulas", response_model=ApiResponse[MaterialFormulasResponse])
async def list_material_formulas(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询资料中的公式和公式解释。"""
    try:
        formulas = await MaterialStructureService.list_formulas(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialFormulasResponse(
            material_id=material_id,
            formulas=[MaterialFormulaResponse.model_validate(formula) for formula in formulas],
        )
    )


@router.get("/{material_id}/structured", response_model=ApiResponse[MaterialStructuredResponse])
async def get_material_structured(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """一次性查询资料章节和 chunks。"""
    try:
        sections = await MaterialStructureService.list_sections(
            db,
            current_user=current_user,
            material_id=material_id,
        )
        chunks = await MaterialStructureService.list_chunks(
            db,
            current_user=current_user,
            material_id=material_id,
        )
        figures = await MaterialStructureService.list_figures(
            db,
            current_user=current_user,
            material_id=material_id,
        )
        tables = await MaterialStructureService.list_tables(
            db,
            current_user=current_user,
            material_id=material_id,
        )
        formulas = await MaterialStructureService.list_formulas(
            db,
            current_user=current_user,
            material_id=material_id,
        )
    except ValueError as exc:
        return fail(code=40402, message=str(exc))

    return success(
        data=MaterialStructuredResponse(
            material_id=material_id,
            sections=[MaterialSectionResponse.model_validate(section) for section in sections],
            chunks=[MaterialChunkResponse.model_validate(chunk) for chunk in chunks],
            figures=[MaterialFigureResponse.model_validate(figure) for figure in figures],
            tables=[MaterialTableResponse.model_validate(table) for table in tables],
            formulas=[MaterialFormulaResponse.model_validate(formula) for formula in formulas],
        )
    )


@router.post("/{material_id}/parse", response_model=ApiResponse[MaterialDetailResponse])
async def parse_material(
    background_tasks: BackgroundTasks,
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """资料解析接口。

    创建后台解析任务，立即返回 parsing 状态。TXT、PDF 和图片 OCR 的具体
    解析结果可通过资料详情或列表接口轮询查看。
    """
    try:
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )
        material, task = await ParserService.enqueue_material_parse(db, material=material)
        background_tasks.add_task(ParserService.parse_material_by_task_id, task.id)
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
