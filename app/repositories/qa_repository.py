from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa import QaRecord


class QaRepository:
    """QA 问答记录的数据访问层。

    service 层负责组织业务流程，repository 层只关心数据库如何查询和写入。
    这样后续增加历史记录、分页、按资料筛选时，不需要把 SQLAlchemy 细节散落
    到 router 或 service 中。
    """

    @staticmethod
    async def create_qa_record(
        db: AsyncSession,
        *,
        user_id: int,
        material_id: int,
        question: str,
        answer: str,
        references: list[dict[str, int | str]],
        ai_provider: str,
        ai_model: str | None,
    ) -> QaRecord:
        """保存一次用户提问和 AI 回答。

        references 保存为 JSON，当前结构为：
        [{"material_id": 1, "snippet": "引用片段"}]
        """
        record = QaRecord(
            user_id=user_id,
            material_id=material_id,
            question=question,
            answer=answer,
            references=references,
            ai_provider=ai_provider,
            ai_model=ai_model,
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        return record


    @staticmethod
    async def list_qa_records(
        db: AsyncSession,
        *,
        user_id: int,
        material_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[QaRecord], int]:
        """按用户列出 QA 历史记录。

        material_id 可选，用于只查看某一份资料下的问答历史。
        user_id 是必选条件，保证学生不能看到其他用户的问答记录。
        """
        conditions = [QaRecord.user_id == user_id]
        if material_id is not None:
            conditions.append(QaRecord.material_id == material_id)

        total_result = await db.execute(
            select(func.count()).select_from(QaRecord).where(*conditions)
        )
        total = int(total_result.scalar_one())

        offset = (page - 1) * page_size
        items_result = await db.execute(
            select(QaRecord)
            .where(*conditions)
            .order_by(QaRecord.created_at.desc(), QaRecord.id.desc())
            .offset(offset)
            .limit(page_size)
        )

        return list(items_result.scalars().all()), total
