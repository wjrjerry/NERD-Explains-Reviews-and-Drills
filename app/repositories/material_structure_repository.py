from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material, MaterialParseStatus
from app.models.material_structure import MaterialChunk, MaterialFigure, MaterialFormula, MaterialSection, MaterialTable


class MaterialStructureRepository:
    """资料结构化解析结果仓储。"""

    @staticmethod
    async def clear_for_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> None:
        """清理某份资料的结构化解析结果。"""
        await db.execute(delete(MaterialFormula).where(MaterialFormula.material_id == material_id))
        await db.execute(delete(MaterialTable).where(MaterialTable.material_id == material_id))
        await db.execute(delete(MaterialFigure).where(MaterialFigure.material_id == material_id))
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
        figures: list[MaterialFigure] | None = None,
        tables: list[MaterialTable] | None = None,
        formulas: list[MaterialFormula] | None = None,
    ) -> tuple[
        list[MaterialSection],
        list[MaterialChunk],
        list[MaterialFigure],
        list[MaterialTable],
        list[MaterialFormula],
    ]:
        """替换某份资料的章节和 chunks。

        重新解析资料时需要先清理旧结构化结果，避免 B 模块读到过期内容。
        """
        figures = figures or []
        tables = tables or []
        formulas = formulas or []

        await db.execute(delete(MaterialFormula).where(MaterialFormula.material_id == material_id))
        await db.execute(delete(MaterialTable).where(MaterialTable.material_id == material_id))
        await db.execute(delete(MaterialFigure).where(MaterialFigure.material_id == material_id))
        await db.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material_id))
        await db.execute(delete(MaterialSection).where(MaterialSection.material_id == material_id))
        await db.flush()

        for section in sections:
            db.add(section)
        await db.flush()

        for chunk in chunks:
            db.add(chunk)
        for figure in figures:
            db.add(figure)
        for table in tables:
            db.add(table)
        for formula in formulas:
            db.add(formula)

        await db.commit()

        for section in sections:
            await db.refresh(section)
        for chunk in chunks:
            await db.refresh(chunk)
        for figure in figures:
            await db.refresh(figure)
        for table in tables:
            await db.refresh(table)
        for formula in formulas:
            await db.refresh(formula)

        return sections, chunks, figures, tables, formulas

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
    async def list_figures_by_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> list[MaterialFigure]:
        result = await db.execute(
            select(MaterialFigure)
            .where(MaterialFigure.material_id == material_id)
            .order_by(MaterialFigure.order_index.asc(), MaterialFigure.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_tables_by_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> list[MaterialTable]:
        result = await db.execute(
            select(MaterialTable)
            .where(MaterialTable.material_id == material_id)
            .order_by(MaterialTable.order_index.asc(), MaterialTable.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_formulas_by_material(
        db: AsyncSession,
        *,
        material_id: int,
    ) -> list[MaterialFormula]:
        result = await db.execute(
            select(MaterialFormula)
            .where(MaterialFormula.material_id == material_id)
            .order_by(MaterialFormula.order_index.asc(), MaterialFormula.id.asc())
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
