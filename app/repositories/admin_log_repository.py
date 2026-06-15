from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_log import AdminLog


class AdminLogRepository:
    """管理员操作日志仓储。"""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        admin_user_id: int,
        operation_type: str,
        target_type: str,
        target_id: int | None,
        operation_result: str,
        remark: str | None = None,
    ) -> AdminLog:
        """创建管理员操作日志。"""
        log = AdminLog(
            admin_user_id=admin_user_id,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            operation_result=operation_result,
            remark=remark,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        *,
        page: int,
        page_size: int,
        admin_user_id: int | None = None,
        operation_type: str | None = None,
        target_type: str | None = None,
        operation_result: str | None = None,
    ) -> tuple[list[AdminLog], int]:
        """分页查询管理员操作日志。"""
        conditions = []
        if admin_user_id is not None:
            conditions.append(AdminLog.admin_user_id == admin_user_id)
        if operation_type is not None:
            conditions.append(AdminLog.operation_type == operation_type)
        if target_type is not None:
            conditions.append(AdminLog.target_type == target_type)
        if operation_result is not None:
            conditions.append(AdminLog.operation_result == operation_result)

        total_result = await db.execute(
            select(func.count()).select_from(AdminLog).where(*conditions)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(AdminLog)
            .where(*conditions)
            .order_by(AdminLog.created_at.desc(), AdminLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
