from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material, MaterialParseStatus


class MaterialRepository:
    """资料数据访问仓储。

    负责封装 materials 表的查询与写入操作，保证服务层不直接拼接数据库语句。
    """

    @staticmethod
    async def create(db: AsyncSession, material: Material) -> Material:
        """创建资料记录。"""
        db.add(material)
        await db.commit()
        await db.refresh(material)

        return material

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        material_id: int,
        user_id: int,
    ) -> Material | None:
        """根据资料 ID 和用户 ID 查询未删除资料。

        user_id 用于保证学生只能访问自己的资料。
        """
        result = await db.execute(
            select(Material).where(
                Material.id == material_id,
                Material.user_id == user_id,
                Material.is_deleted.is_(False),
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
        target_id: int | None = None,
    ) -> tuple[list[Material], int]:
        """分页查询当前用户的资料列表。

        target_id 可选，用于筛选某个课程/考试目标下的资料。
        """
        conditions = [
            Material.user_id == user_id,
            Material.is_deleted.is_(False),
        ]

        if target_id is not None:
            conditions.append(Material.target_id == target_id)

        total_result = await db.execute(
            select(func.count()).select_from(Material).where(*conditions)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Material)
            .where(*conditions)
            .order_by(Material.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(result.scalars().all()), total

    @staticmethod
    async def soft_delete(db: AsyncSession, material: Material) -> Material:
        """软删除资料记录。"""
        material.is_deleted = True

        db.add(material)
        await db.commit()
        await db.refresh(material)

        return material

    @staticmethod
    async def update_parse_result(
        db: AsyncSession,
        material: Material,
        *,
        parse_status: MaterialParseStatus,
        parsed_text: str | None = None,
        parse_error: str | None = None,
    ) -> Material:
        """更新资料解析结果。

        用于记录资料解析过程中的状态变化、解析文本和失败原因。
        """
        material.parse_status = parse_status
        material.parsed_text = parsed_text
        material.parse_error = parse_error

        db.add(material)
        await db.commit()
        await db.refresh(material)

        return material
