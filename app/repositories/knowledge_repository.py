"""Database access for AI knowledge extraction results."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeExtraction,
    KnowledgeExtractionScope,
    KnowledgeExtractionStatus,
)


class KnowledgeRepository:
    """Repository for material-level and target-level knowledge extractions."""

    @staticmethod
    async def save_extraction(
        db: AsyncSession,
        *,
        user_id: int,
        scope: KnowledgeExtractionScope,
        target_id: int | None,
        material_id: int | None,
        summary: str,
        outline: list[str],
        keywords: list[str],
        key_points: list[str],
        exam_points: list[str],
        status: KnowledgeExtractionStatus = KnowledgeExtractionStatus.completed,
        error_message: str | None = None,
    ) -> KnowledgeExtraction:
        """Insert one extraction snapshot and return it."""
        row = KnowledgeExtraction(
            user_id=user_id,
            scope=scope,
            target_id=target_id,
            material_id=material_id,
            status=status,
            summary=summary,
            outline=outline,
            keywords=keywords,
            key_points=key_points,
            exam_points=exam_points,
            error_message=error_message,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def get_latest(
        db: AsyncSession,
        *,
        user_id: int,
        scope: KnowledgeExtractionScope,
        target_id: int | None = None,
        material_id: int | None = None,
    ) -> KnowledgeExtraction | None:
        """Return the latest extraction for one material or target."""
        conditions = [
            KnowledgeExtraction.user_id == user_id,
            KnowledgeExtraction.scope == scope,
        ]
        if target_id is not None:
            conditions.append(KnowledgeExtraction.target_id == target_id)
        if material_id is not None:
            conditions.append(KnowledgeExtraction.material_id == material_id)

        result = await db.execute(
            select(KnowledgeExtraction)
            .where(*conditions)
            .order_by(KnowledgeExtraction.created_at.desc(), KnowledgeExtraction.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_latest_material_extractions_by_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> list[KnowledgeExtraction]:
        """Return the latest material-level extraction for each material."""
        result = await db.execute(
            select(KnowledgeExtraction)
            .where(
                KnowledgeExtraction.user_id == user_id,
                KnowledgeExtraction.target_id == target_id,
                KnowledgeExtraction.scope == KnowledgeExtractionScope.material,
            )
            .order_by(
                KnowledgeExtraction.material_id.asc(),
                KnowledgeExtraction.created_at.desc(),
                KnowledgeExtraction.id.desc(),
            )
        )

        latest_by_material: dict[int, KnowledgeExtraction] = {}
        for row in result.scalars().all():
            if row.material_id is None or row.material_id in latest_by_material:
                continue
            latest_by_material[row.material_id] = row
        return list(latest_by_material.values())
