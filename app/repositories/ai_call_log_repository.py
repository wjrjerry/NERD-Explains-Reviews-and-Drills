"""Data access layer for AI call logs and usage summaries."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_call_log import AiCallLog, AiCallStatus


class AiCallLogRepository:
    """Repository for token usage and local billing logs."""

    @staticmethod
    async def create_many(
        db: AsyncSession,
        *,
        rows: list[dict[str, object]],
    ) -> list[AiCallLog]:
        """Persist a batch of AI call logs."""
        logs = [AiCallLog(**row) for row in rows]
        if not logs:
            return []

        db.add_all(logs)
        await db.commit()
        for log in logs:
            await db.refresh(log)
        return logs

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int | None,
        material_id: int | None,
        feature: str | None,
        status: AiCallStatus | None,
        start_at: datetime | None,
        end_at: datetime | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AiCallLog], int]:
        """List current user's logs with optional filters."""
        conditions = [AiCallLog.user_id == user_id]
        if target_id is not None:
            conditions.append(AiCallLog.target_id == target_id)
        if material_id is not None:
            conditions.append(AiCallLog.material_id == material_id)
        if feature is not None:
            conditions.append(AiCallLog.feature == feature)
        if status is not None:
            conditions.append(AiCallLog.status == status)
        if start_at is not None:
            conditions.append(AiCallLog.created_at >= start_at)
        if end_at is not None:
            conditions.append(AiCallLog.created_at <= end_at)

        total_result = await db.execute(
            select(func.count()).select_from(AiCallLog).where(*conditions)
        )
        total = int(total_result.scalar_one())

        rows_result = await db.execute(
            select(AiCallLog)
            .where(*conditions)
            .order_by(AiCallLog.created_at.desc(), AiCallLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows_result.scalars().all()), total

    @staticmethod
    async def summarize(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int | None,
        material_id: int | None,
        start_at: datetime | None,
        end_at: datetime | None,
    ) -> dict[str, object]:
        """Aggregate current user's token usage and local estimated cost."""
        conditions = [AiCallLog.user_id == user_id]
        if target_id is not None:
            conditions.append(AiCallLog.target_id == target_id)
        if material_id is not None:
            conditions.append(AiCallLog.material_id == material_id)
        if start_at is not None:
            conditions.append(AiCallLog.created_at >= start_at)
        if end_at is not None:
            conditions.append(AiCallLog.created_at <= end_at)

        total_result = await db.execute(
            select(
                func.count(AiCallLog.id),
                func.coalesce(func.sum(AiCallLog.prompt_tokens), 0),
                func.coalesce(func.sum(AiCallLog.completion_tokens), 0),
                func.coalesce(func.sum(AiCallLog.total_tokens), 0),
                func.coalesce(func.sum(AiCallLog.estimated_cost), Decimal("0")),
            ).where(*conditions)
        )
        total_calls, prompt_tokens, completion_tokens, total_tokens, estimated_cost = (
            total_result.one()
        )

        by_feature_result = await db.execute(
            select(
                AiCallLog.feature,
                func.count(AiCallLog.id),
                func.coalesce(func.sum(AiCallLog.prompt_tokens), 0),
                func.coalesce(func.sum(AiCallLog.completion_tokens), 0),
                func.coalesce(func.sum(AiCallLog.total_tokens), 0),
                func.coalesce(func.sum(AiCallLog.estimated_cost), Decimal("0")),
            )
            .where(*conditions)
            .group_by(AiCallLog.feature)
            .order_by(func.coalesce(func.sum(AiCallLog.estimated_cost), Decimal("0")).desc())
        )

        return {
            "total_calls": int(total_calls),
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
            "estimated_cost": estimated_cost,
            "by_feature": list(by_feature_result.all()),
        }
