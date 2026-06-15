from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import (
    Question,
    QuestionDifficulty,
    QuestionKnowledgePoint,
    QuestionType,
)


class QuestionRepository:
    """AI-generated question data access layer."""

    @staticmethod
    async def create_questions(
        db: AsyncSession,
        *,
        user_id: int,
        material_id: int,
        target_id: int | None = None,
        knowledge_point_ids: list[int] | None = None,
        questions: list[dict[str, object]],
    ) -> list[Question]:
        """Bulk insert generated questions and return saved rows."""
        default_point_ids = list(dict.fromkeys(knowledge_point_ids or []))
        rows = [
            Question(
                user_id=user_id,
                material_id=material_id,
                target_id=target_id,
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
                hints=[
                    str(hint) for hint in question.get("hints", []) if str(hint).strip()
                ],
                knowledge_points=[
                    str(point) for point in question["knowledge_points"]
                ],
                difficulty=QuestionDifficulty(str(question["difficulty"])),
            )
            for question in questions
        ]

        db.add_all(rows)
        await db.flush()

        link_rows: list[QuestionKnowledgePoint] = []
        for row, question in zip(rows, questions, strict=True):
            question_point_ids = question.get("knowledge_point_ids", default_point_ids)
            if not isinstance(question_point_ids, list):
                question_point_ids = default_point_ids
            for point_id in list(dict.fromkeys(question_point_ids)):
                try:
                    normalized_point_id = int(point_id)
                except (TypeError, ValueError):
                    continue
                link_rows.append(
                    QuestionKnowledgePoint(
                        question_id=row.id,
                        knowledge_point_id=normalized_point_id,
                        relevance_score=1.0,
                    )
                )

        if link_rows:
            db.add_all(link_rows)

        await db.commit()
        for row in rows:
            await db.refresh(row)

        return rows

    @staticmethod
    async def list_knowledge_point_ids_by_question_ids(
        db: AsyncSession,
        *,
        question_ids: list[int],
    ) -> dict[int, list[int]]:
        """Return linked knowledge point IDs keyed by question_id."""
        if not question_ids:
            return {}

        result = await db.execute(
            select(
                QuestionKnowledgePoint.question_id,
                QuestionKnowledgePoint.knowledge_point_id,
            )
            .where(QuestionKnowledgePoint.question_id.in_(question_ids))
            .order_by(QuestionKnowledgePoint.question_id.asc(), QuestionKnowledgePoint.id.asc())
        )
        links: dict[int, list[int]] = {}
        for question_id, point_id in result.all():
            links.setdefault(int(question_id), []).append(int(point_id))
        return links

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

    @staticmethod
    async def list_by_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        limit: int = 500,
    ) -> list[Question]:
        """List generated questions under one target for export."""
        result = await db.execute(
            select(Question)
            .where(
                Question.user_id == user_id,
                Question.target_id == target_id,
            )
            .order_by(Question.created_at.desc(), Question.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
