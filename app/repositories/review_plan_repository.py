from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.review_plan import ReviewPlan, ReviewPlanTask
from app.models.study_target import StudyTarget


class ReviewPlanRepository:
    """Review plan data access layer."""

    @staticmethod
    async def create_review_plan(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        title: str,
        start_date,
        end_date,
        summary: str,
        tasks: list[dict[str, object]],
    ) -> ReviewPlan:
        """Insert one review plan and its daily tasks."""
        plan = ReviewPlan(
            user_id=user_id,
            target_id=target_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
        )
        db.add(plan)
        await db.flush()

        task_rows = [
            ReviewPlanTask(
                plan_id=plan.id,
                task_date=task["date"],
                title=str(task["title"]),
                content=str(task["content"]),
                material_id=(
                    int(task["material_id"])
                    if task.get("material_id") is not None
                    else None
                ),
                wrong_question_id=(
                    int(task["wrong_question_id"])
                    if task.get("wrong_question_id") is not None
                    else None
                ),
                knowledge_point_id=(
                    int(task["knowledge_point_id"])
                    if task.get("knowledge_point_id") is not None
                    else None
                ),
            )
            for task in tasks
        ]
        db.add_all(task_rows)
        await db.commit()

        result = await db.execute(
            select(ReviewPlan)
            .options(selectinload(ReviewPlan.tasks))
            .where(ReviewPlan.id == plan.id)
        )
        return result.scalar_one()

    @staticmethod
    async def list_review_plans(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ReviewPlan], int]:
        """Query review plans with pagination and optional target filter."""
        conditions = [
            ReviewPlan.user_id == user_id,
            StudyTarget.is_deleted.is_(False),
        ]
        if target_id is not None:
            conditions.append(ReviewPlan.target_id == target_id)

        total_result = await db.execute(
            select(func.count())
            .select_from(ReviewPlan)
            .join(StudyTarget, StudyTarget.id == ReviewPlan.target_id)
            .where(*conditions)
        )
        total = int(total_result.scalar_one())

        result = await db.execute(
            select(ReviewPlan)
            .join(StudyTarget, StudyTarget.id == ReviewPlan.target_id)
            .options(selectinload(ReviewPlan.tasks))
            .where(*conditions)
            .order_by(ReviewPlan.created_at.desc(), ReviewPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        user_id: int,
        plan_id: int,
    ) -> ReviewPlan | None:
        """Fetch one review plan with tasks if it belongs to the user."""
        result = await db.execute(
            select(ReviewPlan)
            .join(StudyTarget, StudyTarget.id == ReviewPlan.target_id)
            .options(selectinload(ReviewPlan.tasks))
            .where(
                ReviewPlan.id == plan_id,
                ReviewPlan.user_id == user_id,
                StudyTarget.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_task_completed(
        db: AsyncSession,
        *,
        user_id: int,
        task_id: int,
        completed: bool,
    ) -> ReviewPlanTask | None:
        """Update one task if it belongs to the user through its parent plan."""
        result = await db.execute(
            select(ReviewPlanTask)
            .join(ReviewPlan, ReviewPlan.id == ReviewPlanTask.plan_id)
            .join(StudyTarget, StudyTarget.id == ReviewPlan.target_id)
            .where(
                ReviewPlanTask.id == task_id,
                ReviewPlan.user_id == user_id,
                StudyTarget.is_deleted.is_(False),
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            return None

        task.completed = completed
        await db.commit()
        await db.refresh(task)
        return task
