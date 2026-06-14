from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.material import MaterialParseStatus
from app.models.parse_task import ParseTaskStatus
from app.models.user import User, UserRole
from app.repositories.admin_log_repository import AdminLogRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.parse_task_repository import ParseTaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin_log import AdminLogResponse
from app.schemas.material import MaterialDetailResponse, MaterialResponse
from app.schemas.parse_task import ParseTaskDetailResponse, ParseTaskResponse
from app.schemas.response import ApiResponse, PageResult
from app.schemas.user import UserResponse
from app.services.parser_service import ParserService
from app.utils.responses import fail, page_result, success

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=ApiResponse[PageResult[UserResponse]])
async def list_users(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    role: UserRole | None = Query(default=None, description="用户角色"),
    is_active: bool | None = Query(default=None, description="是否启用"),
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看用户列表。"""
    users, total = await UserRepository.list_users(
        db,
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
    )

    return success(
        data=page_result(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/materials", response_model=ApiResponse[PageResult[MaterialResponse]])
async def list_materials(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    user_id: int | None = Query(default=None, description="所属用户 ID"),
    target_id: int | None = Query(default=None, description="课程/考试目标 ID"),
    parse_status: MaterialParseStatus | None = Query(default=None, description="解析状态"),
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看全部资料列表。"""
    materials, total = await MaterialRepository.list_all(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        target_id=target_id,
        parse_status=parse_status,
    )

    return success(
        data=page_result(
            items=[MaterialResponse.model_validate(material) for material in materials],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/tasks", response_model=ApiResponse[PageResult[ParseTaskResponse]])
async def list_failed_tasks(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    status: ParseTaskStatus | None = Query(default=None, description="任务状态"),
    user_id: int | None = Query(default=None, description="所属用户 ID"),
    material_id: int | None = Query(default=None, description="资料 ID"),
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看资料解析任务。

    任务状态来自 parse_tasks 表，支持 pending、running、succeeded、failed。
    """
    tasks, total = await ParseTaskRepository.list_tasks(
        db,
        page=page,
        page_size=page_size,
        status=status,
        user_id=user_id,
        material_id=material_id,
    )

    return success(
        data=page_result(
            items=[ParseTaskResponse.model_validate(task) for task in tasks],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/tasks/{task_id}/retry", response_model=ApiResponse[ParseTaskDetailResponse])
async def retry_parse_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员重新解析失败资料。"""
    task = await ParseTaskRepository.get_by_id(db, task_id)
    if task is None:
        await AdminLogRepository.create(
            db,
            admin_user_id=admin_user.id,
            operation_type="retry_parse",
            target_type="parse_task",
            target_id=task_id,
            operation_result="failed",
            remark="解析任务不存在",
        )
        return fail(code=40403, message="解析任务不存在")

    material = await MaterialRepository.get_by_id_for_admin(db, material_id=task.material_id)
    if material is None:
        await AdminLogRepository.create(
            db,
            admin_user_id=admin_user.id,
            operation_type="retry_parse",
            target_type="parse_task",
            target_id=task_id,
            operation_result="failed",
            remark="资料不存在",
        )
        return fail(code=40402, message="资料不存在")

    task = await ParseTaskRepository.reset_for_retry(db, task)
    await MaterialRepository.update_parse_result(
        db,
        material,
        parse_status=MaterialParseStatus.parsing,
        parsed_text=None,
        parse_error=None,
    )
    background_tasks.add_task(ParserService.parse_material_by_task_id, task.id)

    await AdminLogRepository.create(
        db,
        admin_user_id=admin_user.id,
        operation_type="retry_parse",
        target_type="parse_task",
        target_id=task.id,
        operation_result="success",
        remark=f"管理员触发资料 {material.id} 重新解析",
    )

    return success(
        data=ParseTaskDetailResponse(
            task=ParseTaskResponse.model_validate(task),
        )
    )


@router.get("/logs", response_model=ApiResponse[PageResult[AdminLogResponse]])
async def list_admin_logs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    admin_user_id: int | None = Query(default=None, description="管理员用户 ID"),
    operation_type: str | None = Query(default=None, description="操作类型"),
    target_type: str | None = Query(default=None, description="对象类型"),
    operation_result: str | None = Query(default=None, description="操作结果"),
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看操作日志。"""
    logs, total = await AdminLogRepository.list_logs(
        db,
        page=page,
        page_size=page_size,
        admin_user_id=admin_user_id,
        operation_type=operation_type,
        target_type=target_type,
        operation_result=operation_result,
    )

    return success(
        data=page_result(
            items=[AdminLogResponse.model_validate(log) for log in logs],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
