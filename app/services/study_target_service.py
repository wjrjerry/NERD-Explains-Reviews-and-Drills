from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_target import StudyTarget
from app.models.user import User
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.study_target import StudyTargetCreateRequest, StudyTargetUpdateRequest


class StudyTargetService:
    """课程/考试目标业务服务。

    负责处理目标创建、查询、更新和删除等业务规则。
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        current_user: User,
        payload: StudyTargetCreateRequest,
    ) -> StudyTarget:
        """创建当前用户的课程/考试目标。

        user_id 从当前登录用户中获取，避免前端伪造用户归属。
        """
        target = StudyTarget(
            user_id=current_user.id,
            title=payload.title,
            subject=payload.subject,
            target_type=payload.target_type,
            exam_date=payload.exam_date,
            review_goal=payload.review_goal,
            description=payload.description,
        )

        return await StudyTargetRepository.create(db, target)

    @staticmethod
    async def list_by_current_user(
        db: AsyncSession,
        *,
        current_user: User,
        page: int,
        page_size: int,
    ) -> tuple[list[StudyTarget], int]:
        """分页查询当前用户的课程/考试目标。"""
        return await StudyTargetRepository.list_by_user(
            db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_detail(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
    ) -> StudyTarget:
        """获取当前用户的课程/考试目标详情。"""
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")

        return target

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
        payload: StudyTargetUpdateRequest,
    ) -> StudyTarget:
        """更新当前用户的课程/考试目标。"""
        target = await StudyTargetService.get_detail(
            db,
            current_user=current_user,
            target_id=target_id,
        )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(target, field, value)

        return await StudyTargetRepository.update(db, target)

    @staticmethod
    async def delete(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
    ) -> StudyTarget:
        """软删除当前用户的课程/考试目标。"""
        target = await StudyTargetService.get_detail(
            db,
            current_user=current_user,
            target_id=target_id,
        )

        return await StudyTargetRepository.soft_delete(db, target)