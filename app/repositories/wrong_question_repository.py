from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wrong_question import MasteryStatus, WrongQuestion


class WrongQuestionRepository:
    """Wrong-question book data access layer."""

    @staticmethod
    async def create_wrong_questions(
        db: AsyncSession,
        *,
        user_id: int,
        test_record_id: int,
        wrong_items: list[dict[str, object]],
    ) -> list[WrongQuestion]:
        """Bulk insert wrong-question records after a test submission."""
        rows = [
            WrongQuestion(
                user_id=user_id,
                test_record_id=test_record_id,
                question_id=int(item["question_id"]),
                target_id=(
                    int(item["target_id"]) if item.get("target_id") is not None else None
                ),
                material_id=int(item["material_id"]),
                stem=str(item["stem"]),
                user_answer=[str(answer) for answer in item["user_answer"]],
                correct_answer=[str(answer) for answer in item["correct_answer"]],
                analysis=str(item["analysis"]),
                wrong_reason=str(item["wrong_reason"]),
                knowledge_points=[str(point) for point in item["knowledge_points"]],
                mastery_status=MasteryStatus.unmastered,
            )
            for item in wrong_items
        ]

        if not rows:
            return []

        db.add_all(rows)
        await db.commit()
        for row in rows:
            await db.refresh(row)

        return rows

    @staticmethod
    async def list_wrong_questions(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int | None = None,
        material_id: int | None = None,
        mastery_status: MasteryStatus | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[WrongQuestion], int]:
        """Query wrong questions with pagination and optional filters."""
        conditions = [WrongQuestion.user_id == user_id]
        if target_id is not None:
            conditions.append(WrongQuestion.target_id == target_id)
        if material_id is not None:
            conditions.append(WrongQuestion.material_id == material_id)
        if mastery_status is not None:
            conditions.append(WrongQuestion.mastery_status == mastery_status)

        total_result = await db.execute(
            select(func.count()).select_from(WrongQuestion).where(*conditions)
        )
        total = int(total_result.scalar_one())

        result = await db.execute(
            select(WrongQuestion)
            .where(*conditions)
            .order_by(WrongQuestion.created_at.desc(), WrongQuestion.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_wrong_question_by_id(
        db: AsyncSession,
        *,
        user_id: int,
        wrong_question_id: int,
    ) -> WrongQuestion | None:
        """Fetch one wrong-question record by ID and ownership."""
        result = await db.execute(
            select(WrongQuestion).where(
                WrongQuestion.id == wrong_question_id,
                WrongQuestion.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_mastery_status(
        db: AsyncSession,
        *,
        user_id: int,
        wrong_question_id: int,
        mastery_status: MasteryStatus,
    ) -> WrongQuestion | None:
        """Update the mastery status of one wrong question."""
        wrong_question = await WrongQuestionRepository.get_wrong_question_by_id(
            db,
            user_id=user_id,
            wrong_question_id=wrong_question_id,
        )
        if wrong_question is None:
            return None

        wrong_question.mastery_status = mastery_status
        db.add(wrong_question)
        await db.commit()
        await db.refresh(wrong_question)

        return wrong_question
