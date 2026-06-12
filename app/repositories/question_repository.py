from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, QuestionDifficulty, QuestionType


class QuestionRepository:
    """AI-generated question data access layer."""

    @staticmethod
    async def create_questions(
        db: AsyncSession,
        *,
        user_id: int,
        material_id: int,
        questions: list[dict[str, object]],
    ) -> list[Question]:
        """Bulk insert generated questions and return saved rows."""
        rows = [
            Question(
                user_id=user_id,
                material_id=material_id,
                question_type=QuestionType(str(question["type"])),
                stem=str(question["stem"]),
                options=[
                    {
                        "key": str(option["key"]),
                        "text": str(option["text"]),
                        "analysis": str(option.get("analysis", "")),
                    }
                    for option in question["options"]
                ],
                correct_answer=[
                    str(answer) for answer in question["correct_answer"]
                ],
                analysis=str(question["analysis"]),
                knowledge_points=[
                    str(point) for point in question["knowledge_points"]
                ],
                difficulty=QuestionDifficulty(str(question["difficulty"])),
            )
            for question in questions
        ]

        db.add_all(rows)
        await db.commit()
        for row in rows:
            await db.refresh(row)

        return rows

    @staticmethod
    async def get_question_by_id(
        db: AsyncSession,
        *,
        user_id: int,
        question_id: int,
    ) -> Question | None:
        """Fetch one generated question if it belongs to the current user."""
        result = await db.execute(
            select(Question).where(
                Question.id == question_id,
                Question.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_ids(
        db: AsyncSession,
        *,
        user_id: int,
        question_ids: list[int],
    ) -> list[Question]:
        """Fetch generated questions by IDs for later test scoring."""
        if not question_ids:
            return []

        result = await db.execute(
            select(Question).where(
                Question.user_id == user_id,
                Question.id.in_(question_ids),
            )
        )
        return list(result.scalars().all())
