from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_target import StudyTarget


class StudyTargetRepository:
    """课程/考试目标数据访问仓储。

    负责封装 study_targets 表的查询与写入操作，保证业务层不直接拼接数据库语句。
    """

    @staticmethod
    async def create(db: AsyncSession, target: StudyTarget) -> StudyTarget:
        """创建课程/考试目标记录。"""
        db.add(target)
        await db.commit()
        await db.refresh(target)

        return target

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        target_id: int,
        user_id: int,
    ) -> StudyTarget | None:
        """根据目标 ID 和用户 ID 查询未删除目标。

        user_id 用于保证学生只能访问自己的课程/考试目标。
        """
        result = await db.execute(
            select(StudyTarget).where(
                StudyTarget.id == target_id,
                StudyTarget.user_id == user_id,
                StudyTarget.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        *,
        user_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyTarget], int]:
        """分页查询当前用户的课程/考试目标。"""
        conditions = (
            StudyTarget.user_id == user_id,
            StudyTarget.is_deleted.is_(False),
        )

        total_result = await db.execute(
            select(func.count()).select_from(StudyTarget).where(*conditions)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(StudyTarget)
            .where(*conditions)
            .order_by(StudyTarget.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(result.scalars().all()), total

    @staticmethod
    async def update(db: AsyncSession, target: StudyTarget) -> StudyTarget:
        """更新课程/考试目标记录。"""
        db.add(target)
        await db.commit()
        await db.refresh(target)

        return target

    @staticmethod
    async def soft_delete(db: AsyncSession, target: StudyTarget) -> StudyTarget:
        """软删除课程/考试目标记录。"""
        target.is_deleted = True

        db.add(target)
        await db.commit()
        await db.refresh(target)

        return target