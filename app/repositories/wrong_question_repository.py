from datetime import datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.wrong_question import (
    MasteryStatus,
    WrongQuestion,
    WrongQuestionKnowledgePoint,
)


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
        rows: list[WrongQuestion] = []
        point_ids_by_index: list[list[int]] = []
        for item in wrong_items:
            rows.append(
                WrongQuestion(
                    user_id=user_id,
                    test_record_id=test_record_id,
                    question_id=int(item["question_id"]),
                    target_id=(
                        int(item["target_id"])
                        if item.get("target_id") is not None
                        else None
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
            )
            raw_point_ids = item.get("knowledge_point_ids", [])
            if not isinstance(raw_point_ids, list):
                raw_point_ids = []
            normalized_point_ids: list[int] = []
            for point_id in raw_point_ids:
                try:
                    normalized_point_ids.append(int(point_id))
                except (TypeError, ValueError):
                    continue
            point_ids_by_index.append(list(dict.fromkeys(normalized_point_ids)))

        if not rows:
            return []

        db.add_all(rows)
        await db.flush()

        link_rows: list[WrongQuestionKnowledgePoint] = []
        for row, point_ids in zip(rows, point_ids_by_index, strict=True):
            for point_id in point_ids:
                link_rows.append(
                    WrongQuestionKnowledgePoint(
                        wrong_question_id=row.id,
                        knowledge_point_id=point_id,
                        wrong_reason=row.wrong_reason,
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
    async def list_knowledge_point_ids_by_wrong_question_ids(
        db: AsyncSession,
        *,
        wrong_question_ids: list[int],
    ) -> dict[int, list[int]]:
        """Return linked knowledge point IDs keyed by wrong_question_id."""
        if not wrong_question_ids:
            return {}

        result = await db.execute(
            select(
                WrongQuestionKnowledgePoint.wrong_question_id,
                WrongQuestionKnowledgePoint.knowledge_point_id,
            )
            .where(WrongQuestionKnowledgePoint.wrong_question_id.in_(wrong_question_ids))
            .order_by(
                WrongQuestionKnowledgePoint.wrong_question_id.asc(),
                WrongQuestionKnowledgePoint.id.asc(),
            )
        )
        links: dict[int, list[int]] = {}
        for wrong_question_id, point_id in result.all():
            links.setdefault(int(wrong_question_id), []).append(int(point_id))
        return links

    @staticmethod
    async def list_wrong_questions(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int | None = None,
        material_id: int | None = None,
        knowledge_point_id: int | None = None,
        mastery_status: MasteryStatus | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[WrongQuestion], int]:
        """Query wrong questions with pagination and optional filters."""
        conditions = [WrongQuestion.user_id == user_id]
        from_clause = select(WrongQuestion)
        if target_id is not None:
            conditions.append(WrongQuestion.target_id == target_id)
        if material_id is not None:
            conditions.append(WrongQuestion.material_id == material_id)
        if knowledge_point_id is not None:
            conditions.append(
                WrongQuestionKnowledgePoint.knowledge_point_id == knowledge_point_id
            )
            from_clause = from_clause.join(
                WrongQuestionKnowledgePoint,
                WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
            )
        if mastery_status is not None:
            conditions.append(WrongQuestion.mastery_status == mastery_status)

        if knowledge_point_id is None:
            total_query = select(func.count()).select_from(WrongQuestion).where(*conditions)
        else:
            total_query = (
                select(func.count())
                .select_from(WrongQuestion)
                .join(
                    WrongQuestionKnowledgePoint,
                    WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
                )
                .where(*conditions)
            )
        total_result = await db.execute(total_query)
        total = int(total_result.scalar_one())

        result = await db.execute(
            from_clause
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
        reviewed_at: datetime | None = None,
        next_review_at: datetime | None = None,
        increment_review_count: bool = False,
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
        if reviewed_at is not None:
            wrong_question.last_reviewed_at = reviewed_at
        wrong_question.next_review_at = next_review_at
        if increment_review_count:
            wrong_question.review_count += 1
        db.add(wrong_question)
        await db.commit()
        await db.refresh(wrong_question)

        return wrong_question

    @staticmethod
    async def list_review_candidates(
        db: AsyncSession,
        *,
        user_id: int,
        mastery_status: MasteryStatus,
        target_id: int | None = None,
        knowledge_point_id: int | None = None,
        due_at: datetime | None = None,
        due_only: bool = False,
        exclude_ids: set[int] | None = None,
        limit: int = 10,
    ) -> list[WrongQuestion]:
        """Return review candidates for one status bucket."""
        conditions = [
            WrongQuestion.user_id == user_id,
            WrongQuestion.mastery_status == mastery_status,
        ]
        if target_id is not None:
            conditions.append(WrongQuestion.target_id == target_id)
        if knowledge_point_id is not None:
            conditions.append(WrongQuestionKnowledgePoint.knowledge_point_id == knowledge_point_id)
        if exclude_ids:
            conditions.append(WrongQuestion.id.notin_(exclude_ids))
        if due_only and due_at is not None:
            conditions.append(
                or_(
                    WrongQuestion.review_count == 0,
                    WrongQuestion.next_review_at.is_(None),
                    WrongQuestion.next_review_at <= due_at,
                )
            )

        query = (
            select(
                WrongQuestion,
                func.coalesce(func.max(KnowledgePoint.importance_weight), 0).label("importance"),
            )
            .select_from(WrongQuestion)
            .outerjoin(
                WrongQuestionKnowledgePoint,
                WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
            )
            .outerjoin(
                KnowledgePoint,
                KnowledgePoint.id == WrongQuestionKnowledgePoint.knowledge_point_id,
            )
            .where(*conditions)
            .group_by(WrongQuestion.id)
            .order_by(
                WrongQuestion.review_count.asc(),
                WrongQuestion.next_review_at.asc().nullsfirst(),
                desc("importance"),
                func.random(),
                WrongQuestion.created_at.asc(),
            )
            .limit(limit)
        )
        result = await db.execute(query)
        return [row[0] for row in result.all()]
