from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material, MaterialParseStatus
from app.models.material_structure import MaterialChunk, MaterialSection


class MaterialStructureRepository:
    """资料结构化解析结果仓储。"""

    @staticmethod
    async def clear_for_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> None:
        """清理某份资料的结构化解析结果。"""
        await db.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material_id))
        await db.execute(delete(MaterialSection).where(MaterialSection.material_id == material_id))
        await db.commit()

    @staticmethod
    async def replace_for_material(
        db: AsyncSession,
        *,
        material_id: int,
        sections: list[MaterialSection],
        chunks: list[MaterialChunk],
    ) -> tuple[list[MaterialSection], list[MaterialChunk]]:
        """替换某份资料的章节和 chunks。

        重新解析资料时需要先清理旧结构化结果，避免 B 模块读到过期内容。
        """
        await db.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material_id))
        await db.execute(delete(MaterialSection).where(MaterialSection.material_id == material_id))
        await db.flush()

        for section in sections:
            db.add(section)
        await db.flush()

        for chunk in chunks:
            db.add(chunk)

        await db.commit()

        for section in sections:
            await db.refresh(section)
        for chunk in chunks:
            await db.refresh(chunk)

        return sections, chunks

    @staticmethod
    async def list_sections_by_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> list[MaterialSection]:
        result = await db.execute(
            select(MaterialSection)
            .where(MaterialSection.material_id == material_id)
            .order_by(MaterialSection.order_index.asc(), MaterialSection.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_chunks_by_material(
        db: AsyncSession,
        *,
        material_id: int,
        section_id: int | None = None,
    ) -> list[MaterialChunk]:
        conditions = [MaterialChunk.material_id == material_id]
        if section_id is not None:
            conditions.append(MaterialChunk.section_id == section_id)

        result = await db.execute(
            select(MaterialChunk)
            .where(*conditions)
            .order_by(MaterialChunk.order_index.asc(), MaterialChunk.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_chunks_by_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        limit: int,
    ) -> list[MaterialChunk]:
        result = await db.execute(
            select(MaterialChunk)
            .join(Material, MaterialChunk.material_id == Material.id)
            .where(
                Material.user_id == user_id,
                Material.target_id == target_id,
                Material.parse_status == MaterialParseStatus.parsed,
                Material.is_deleted.is_(False),
            )
            .order_by(Material.id.asc(), MaterialChunk.order_index.asc(), MaterialChunk.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
