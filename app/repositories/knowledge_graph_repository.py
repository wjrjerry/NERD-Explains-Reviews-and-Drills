"""Data access layer for target-level knowledge graphs."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import (
    KnowledgePoint,
    KnowledgePointSource,
    MasteryStatus,
    MaterialKnowledgePoint,
    UserKnowledgeMastery,
)
from app.models.material import Material
from app.models.question import Question, QuestionKnowledgePoint
from app.models.wrong_question import WrongQuestion, WrongQuestionKnowledgePoint


@dataclass(frozen=True)
class KnowledgePointCreateData:
    """Normalized data needed to create one graph node."""

    name: str
    description: str | None
    importance_weight: float
    parent_name: str | None
    level: int
    sort_order: int
    evidence: list[dict[str, object]]


class KnowledgeGraphRepository:
    """Repository for knowledge points, material links, and mastery rows."""

    @staticmethod
    async def list_points_by_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> list[KnowledgePoint]:
        """List all knowledge points for one target."""
        result = await db.execute(
            select(KnowledgePoint)
            .where(
                KnowledgePoint.user_id == user_id,
                KnowledgePoint.target_id == target_id,
            )
            .order_by(KnowledgePoint.level.asc(), KnowledgePoint.sort_order.asc(), KnowledgePoint.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_point_by_id(
        db: AsyncSession,
        *,
        user_id: int,
        point_id: int,
    ) -> KnowledgePoint | None:
        """Fetch one knowledge point if it belongs to the current user."""
        result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == point_id,
                KnowledgePoint.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_points_by_ids(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        point_ids: list[int],
    ) -> list[KnowledgePoint]:
        """List selected knowledge points under one target."""
        if not point_ids:
            return []

        result = await db.execute(
            select(KnowledgePoint)
            .where(
                KnowledgePoint.user_id == user_id,
                KnowledgePoint.target_id == target_id,
                KnowledgePoint.id.in_(point_ids),
            )
            .order_by(KnowledgePoint.level.asc(), KnowledgePoint.sort_order.asc(), KnowledgePoint.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def replace_graph_for_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        points: list[KnowledgePointCreateData],
    ) -> list[KnowledgePoint]:
        """Replace all knowledge points for one target after AI output is validated."""
        existing = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=target_id,
        )
        existing_ids = [point.id for point in existing]
        if existing_ids:
            await db.execute(
                delete(KnowledgePoint).where(KnowledgePoint.id.in_(existing_ids))
            )
            await db.flush()

        created_by_name: dict[str, KnowledgePoint] = {}
        rows: list[KnowledgePoint] = []

        for item in sorted(points, key=lambda point: (point.level, point.sort_order)):
            parent = created_by_name.get(item.parent_name or "")
            row = KnowledgePoint(
                user_id=user_id,
                target_id=target_id,
                parent_id=parent.id if parent is not None else None,
                name=item.name,
                description=item.description,
                importance_weight=item.importance_weight,
                level=item.level,
                sort_order=item.sort_order,
                source=KnowledgePointSource.ai_generated,
            )
            db.add(row)
            await db.flush()
            created_by_name[row.name] = row
            rows.append(row)

            db.add(
                UserKnowledgeMastery(
                    user_id=user_id,
                    target_id=target_id,
                    knowledge_point_id=row.id,
                    mastery_status=MasteryStatus.unlearned,
                    mastery_score=0.0,
                    accuracy=0.0,
                    answered_count=0,
                    wrong_count=0,
                )
            )

            for evidence in item.evidence:
                material_id = evidence.get("material_id")
                if material_id is None:
                    continue
                try:
                    normalized_material_id = int(material_id)
                except (TypeError, ValueError):
                    continue
                db.add(
                    MaterialKnowledgePoint(
                        material_id=normalized_material_id,
                        knowledge_point_id=row.id,
                        relevance_score=float(evidence.get("relevance_score", 1.0) or 1.0),
                        evidence_text=str(evidence.get("snippet", "") or "")[:500],
                    )
                )

        await db.commit()
        for row in rows:
            await db.refresh(row)
        return rows

    @staticmethod
    async def list_mastery_by_point_ids(
        db: AsyncSession,
        *,
        user_id: int,
        point_ids: list[int],
    ) -> dict[int, UserKnowledgeMastery]:
        """Return mastery rows keyed by knowledge_point_id."""
        if not point_ids:
            return {}
        result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point_id.in_(point_ids),
            )
        )
        return {row.knowledge_point_id: row for row in result.scalars().all()}

    @staticmethod
    async def list_material_links_by_point_ids(
        db: AsyncSession,
        *,
        point_ids: list[int],
    ) -> dict[int, list[MaterialKnowledgePoint]]:
        """Return material evidence links keyed by knowledge_point_id."""
        if not point_ids:
            return {}
        result = await db.execute(
            select(MaterialKnowledgePoint)
            .where(MaterialKnowledgePoint.knowledge_point_id.in_(point_ids))
            .order_by(MaterialKnowledgePoint.relevance_score.desc(), MaterialKnowledgePoint.id.asc())
        )
        links: dict[int, list[MaterialKnowledgePoint]] = {}
        for row in result.scalars().all():
            links.setdefault(row.knowledge_point_id, []).append(row)
        return links

    @staticmethod
    async def latest_generated_at(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
    ) -> datetime | None:
        """Return the newest graph node creation time for one target."""
        points = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=target_id,
        )
        if not points:
            return None
        return max(point.created_at for point in points)

    @staticmethod
    async def get_or_create_mastery(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        point_id: int,
    ) -> UserKnowledgeMastery:
        """Return a mastery row, creating the default row when missing."""
        result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.target_id == target_id,
                UserKnowledgeMastery.knowledge_point_id == point_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row

        row = UserKnowledgeMastery(
            user_id=user_id,
            target_id=target_id,
            knowledge_point_id=point_id,
            mastery_status=MasteryStatus.unlearned,
            mastery_score=0.0,
            accuracy=0.0,
            answered_count=0,
            wrong_count=0,
        )
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def list_material_evidence_for_point(
        db: AsyncSession,
        *,
        point_id: int,
    ) -> list[tuple[MaterialKnowledgePoint, Material]]:
        """List material evidence and material metadata for one knowledge point."""
        result = await db.execute(
            select(MaterialKnowledgePoint, Material)
            .join(Material, Material.id == MaterialKnowledgePoint.material_id)
            .where(MaterialKnowledgePoint.knowledge_point_id == point_id)
            .order_by(MaterialKnowledgePoint.relevance_score.desc(), Material.id.asc())
        )
        return [(link, material) for link, material in result.all()]

    @staticmethod
    async def list_questions_for_point(
        db: AsyncSession,
        *,
        user_id: int,
        point_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Question], int]:
        """List generated questions linked to one knowledge point."""
        from sqlalchemy import func

        conditions = [
            Question.user_id == user_id,
            QuestionKnowledgePoint.knowledge_point_id == point_id,
        ]
        total_result = await db.execute(
            select(func.count())
            .select_from(QuestionKnowledgePoint)
            .join(Question, Question.id == QuestionKnowledgePoint.question_id)
            .where(*conditions)
        )
        total = int(total_result.scalar_one())

        result = await db.execute(
            select(Question)
            .join(QuestionKnowledgePoint, Question.id == QuestionKnowledgePoint.question_id)
            .where(*conditions)
            .order_by(Question.created_at.desc(), Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def list_wrong_questions_for_point(
        db: AsyncSession,
        *,
        user_id: int,
        point_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[WrongQuestion], int]:
        """List wrong questions linked to one knowledge point."""
        from sqlalchemy import func

        conditions = [
            WrongQuestion.user_id == user_id,
            WrongQuestionKnowledgePoint.knowledge_point_id == point_id,
            WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
        ]
        total_result = await db.execute(
            select(func.count())
            .select_from(WrongQuestion)
            .join(
                WrongQuestionKnowledgePoint,
                WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
            )
            .where(*conditions)
        )
        total = int(total_result.scalar_one())

        result = await db.execute(
            select(WrongQuestion)
            .join(
                WrongQuestionKnowledgePoint,
                WrongQuestion.id == WrongQuestionKnowledgePoint.wrong_question_id,
            )
            .where(*conditions)
            .order_by(WrongQuestion.created_at.desc(), WrongQuestion.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
