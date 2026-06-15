from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_task import ParseTask, ParseTaskStatus, ParseTaskType


class ParseTaskRepository:
    """资料解析任务仓储。"""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        material_id: int,
        user_id: int,
        task_status: ParseTaskStatus = ParseTaskStatus.pending,
    ) -> ParseTask:
        """创建解析任务。"""
        task = ParseTask(
            material_id=material_id,
            user_id=user_id,
            task_type=ParseTaskType.material_parse,
            task_status=task_status,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_by_id(db: AsyncSession, task_id: int) -> ParseTask | None:
        """按任务 ID 查询解析任务。"""
        result = await db.execute(select(ParseTask).where(ParseTask.id == task_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_by_material_id(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> ParseTask | None:
        """查询某个资料最近一次解析任务。"""
        result = await db.execute(
            select(ParseTask)
            .where(ParseTask.material_id == material_id)
            .order_by(ParseTask.created_at.desc(), ParseTask.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        *,
        page: int,
        page_size: int,
        status: ParseTaskStatus | None = None,
        user_id: int | None = None,
        material_id: int | None = None,
    ) -> tuple[list[ParseTask], int]:
        """管理员分页查询解析任务。"""
        conditions = []
        if status is not None:
            conditions.append(ParseTask.task_status == status)
        if user_id is not None:
            conditions.append(ParseTask.user_id == user_id)
        if material_id is not None:
            conditions.append(ParseTask.material_id == material_id)

        total_result = await db.execute(
            select(func.count()).select_from(ParseTask).where(*conditions)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(ParseTask)
            .where(*conditions)
            .order_by(ParseTask.created_at.desc(), ParseTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def mark_running(db: AsyncSession, task: ParseTask) -> ParseTask:
        """标记任务为执行中。"""
        task.task_status = ParseTaskStatus.running
        task.failure_reason = None
        task.started_at = datetime.now(timezone.utc)
        task.finished_at = None
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def mark_succeeded(db: AsyncSession, task: ParseTask) -> ParseTask:
        """标记任务为成功。"""
        task.task_status = ParseTaskStatus.succeeded
        task.failure_reason = None
        task.finished_at = datetime.now(timezone.utc)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        task: ParseTask,
        *,
        failure_reason: str,
    ) -> ParseTask:
        """标记任务为失败。"""
        task.task_status = ParseTaskStatus.failed
        task.failure_reason = failure_reason
        task.finished_at = datetime.now(timezone.utc)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def reset_for_retry(db: AsyncSession, task: ParseTask) -> ParseTask:
        """将已有任务重置为待执行，并增加重试次数。"""
        task.task_status = ParseTaskStatus.pending
        task.retry_count += 1
        task.failure_reason = None
        task.started_at = None
        task.finished_at = None
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task
