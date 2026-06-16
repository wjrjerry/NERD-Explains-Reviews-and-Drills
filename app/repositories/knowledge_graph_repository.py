"""Data access layer for target-level knowledge graphs."""

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata

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
from app.models.qa import QaKnowledgePoint
from app.models.question import Question, QuestionKnowledgePoint
from app.models.review_plan import ReviewPlan, ReviewPlanTask
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
    def _normalize_point_name(name: str) -> str:
        """Build a stable key while preserving the user-facing point name."""
        normalized = unicodedata.normalize("NFKC", name).casefold()
        return re.sub(r"[\s\-_—–·•:：,，。/\\]+", "", normalized)

    @staticmethod
    def _mastery_status(answered_count: int, accuracy: float) -> MasteryStatus:
        """Map merged answer statistics back to a mastery status."""
        if answered_count <= 0:
            return MasteryStatus.unlearned
        if accuracy < 0.6:
            return MasteryStatus.weak
        if accuracy < 0.85:
            return MasteryStatus.basic
        return MasteryStatus.proficient

    @staticmethod
    def _newer_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
        """Return the newer non-null datetime."""
        if left is None:
            return right
        if right is None:
            return left
        return max(left, right)

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
    async def sync_graph_for_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        points: list[KnowledgePointCreateData],
    ) -> list[KnowledgePoint]:
        """Merge AI output into the existing graph without breaking point IDs."""
        existing = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=target_id,
        )
        rows_by_key = {
            KnowledgeGraphRepository._normalize_point_name(point.name): point
            for point in existing
        }
        generated_rows: list[tuple[KnowledgePoint, KnowledgePointCreateData]] = []
        existing_links_by_point: dict[int, dict[int, MaterialKnowledgePoint]] = {}

        for item in sorted(points, key=lambda point: (point.level, point.sort_order)):
            key = KnowledgeGraphRepository._normalize_point_name(item.name)
            row = rows_by_key.get(key)
            if row is None:
                row = KnowledgePoint(
                    user_id=user_id,
                    target_id=target_id,
                    parent_id=None,
                    name=item.name,
                    description=item.description,
                    importance_weight=item.importance_weight,
                    level=item.level,
                    sort_order=item.sort_order,
                    source=KnowledgePointSource.ai_generated,
                )
                db.add(row)
                await db.flush()
                rows_by_key[key] = row
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
            else:
                row.name = item.name
                row.description = item.description
                row.importance_weight = item.importance_weight
                row.level = item.level
                row.sort_order = item.sort_order
                row.source = KnowledgePointSource.ai_generated
                db.add(row)

            generated_rows.append((row, item))

        await db.flush()

        generated_ids = [row.id for row, _item in generated_rows]
        if generated_ids:
            existing_link_result = await db.execute(
                select(MaterialKnowledgePoint).where(
                    MaterialKnowledgePoint.knowledge_point_id.in_(generated_ids)
                )
            )
            for link in existing_link_result.scalars().all():
                existing_links_by_point.setdefault(link.knowledge_point_id, {})[
                    link.material_id
                ] = link
            await db.execute(
                delete(MaterialKnowledgePoint).where(
                    MaterialKnowledgePoint.knowledge_point_id.in_(generated_ids)
                )
            )

        for row, item in generated_rows:
            parent = (
                rows_by_key.get(
                    KnowledgeGraphRepository._normalize_point_name(item.parent_name)
                )
                if item.parent_name
                else None
            )
            row.parent_id = parent.id if parent is not None and parent.id != row.id else None
            db.add(row)

            merged_evidence: dict[int, dict[str, object]] = {
                material_id: {
                    "material_id": material_id,
                    "snippet": link.evidence_text or "",
                    "relevance_score": link.relevance_score,
                }
                for material_id, link in existing_links_by_point.get(row.id, {}).items()
            }
            for evidence in item.evidence:
                material_id = evidence.get("material_id")
                if material_id is None:
                    continue
                try:
                    normalized_material_id = int(material_id)
                except (TypeError, ValueError):
                    continue
                merged_evidence[normalized_material_id] = {
                    "material_id": normalized_material_id,
                    "snippet": str(evidence.get("snippet", "") or "")[:500],
                    "relevance_score": float(evidence.get("relevance_score", 1.0) or 1.0),
                }

            for evidence in merged_evidence.values():
                db.add(
                    MaterialKnowledgePoint(
                        material_id=int(evidence["material_id"]),
                        knowledge_point_id=row.id,
                        relevance_score=float(evidence.get("relevance_score", 1.0) or 1.0),
                        evidence_text=str(evidence.get("snippet", "") or "")[:500],
                    )
                )

        await db.commit()
        return await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=target_id,
        )

    @staticmethod
    async def _merge_material_links(
        db: AsyncSession,
        *,
        source_id: int,
        target_id: int,
    ) -> None:
        source_result = await db.execute(
            select(MaterialKnowledgePoint).where(
                MaterialKnowledgePoint.knowledge_point_id == source_id
            )
        )
        target_result = await db.execute(
            select(MaterialKnowledgePoint).where(
                MaterialKnowledgePoint.knowledge_point_id == target_id
            )
        )
        target_by_material = {
            row.material_id: row for row in target_result.scalars().all()
        }

        for source_link in source_result.scalars().all():
            target_link = target_by_material.get(source_link.material_id)
            if target_link is None:
                source_link.knowledge_point_id = target_id
                db.add(source_link)
                continue

            if source_link.relevance_score > target_link.relevance_score:
                target_link.relevance_score = source_link.relevance_score
                target_link.evidence_text = source_link.evidence_text
            elif not target_link.evidence_text and source_link.evidence_text:
                target_link.evidence_text = source_link.evidence_text
            db.add(target_link)
            await db.delete(source_link)

    @staticmethod
    async def _merge_unique_point_links(
        db: AsyncSession,
        *,
        model,
        owner_column,
        source_id: int,
        target_id: int,
    ) -> None:
        source_result = await db.execute(
            select(model).where(model.knowledge_point_id == source_id)
        )
        target_result = await db.execute(
            select(model).where(model.knowledge_point_id == target_id)
        )
        target_owner_ids = {
            getattr(row, owner_column.key) for row in target_result.scalars().all()
        }

        for source_link in source_result.scalars().all():
            owner_id = getattr(source_link, owner_column.key)
            if owner_id in target_owner_ids:
                await db.delete(source_link)
                continue
            source_link.knowledge_point_id = target_id
            db.add(source_link)

    @staticmethod
    async def _merge_review_plan_tasks(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        source_id: int,
        target_point_id: int,
    ) -> None:
        result = await db.execute(
            select(ReviewPlanTask)
            .join(ReviewPlan, ReviewPlan.id == ReviewPlanTask.plan_id)
            .where(
                ReviewPlan.user_id == user_id,
                ReviewPlan.target_id == target_id,
                ReviewPlanTask.knowledge_point_id == source_id,
            )
        )
        for task in result.scalars().all():
            task.knowledge_point_id = target_point_id
            db.add(task)

    @staticmethod
    async def _merge_mastery_rows(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        source_id: int,
        target_point_id: int,
    ) -> None:
        result = await db.execute(
            select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.target_id == target_id,
                UserKnowledgeMastery.knowledge_point_id.in_([source_id, target_point_id]),
            )
        )
        rows = {
            row.knowledge_point_id: row for row in result.scalars().all()
        }
        source = rows.get(source_id)
        target = rows.get(target_point_id)
        if source is None:
            return
        if target is None:
            source.knowledge_point_id = target_point_id
            db.add(source)
            return

        target.answered_count += source.answered_count
        target.wrong_count += source.wrong_count
        target.wrong_count = min(target.wrong_count, target.answered_count)
        correct_count = max(target.answered_count - target.wrong_count, 0)
        target.accuracy = (
            round(correct_count / target.answered_count, 4)
            if target.answered_count
            else 0.0
        )
        target.mastery_score = target.accuracy
        target.mastery_status = KnowledgeGraphRepository._mastery_status(
            target.answered_count,
            target.accuracy,
        )
        target.last_practiced_at = KnowledgeGraphRepository._newer_datetime(
            target.last_practiced_at,
            source.last_practiced_at,
        )
        target.next_review_at = KnowledgeGraphRepository._newer_datetime(
            target.next_review_at,
            source.next_review_at,
        )
        db.add(target)
        await db.delete(source)

    @staticmethod
    async def _reparent_children(
        db: AsyncSession,
        *,
        source: KnowledgePoint,
        target: KnowledgePoint,
    ) -> None:
        result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.parent_id == source.id)
        )
        for child in result.scalars().all():
            if child.id == target.id:
                child.parent_id = source.parent_id if source.parent_id != target.id else None
            else:
                child.parent_id = target.id
            db.add(child)

    @staticmethod
    async def merge_points_for_target(
        db: AsyncSession,
        *,
        user_id: int,
        target_id: int,
        merge_mappings: list[dict[str, str]],
    ) -> None:
        """Merge AI-confirmed duplicate graph points and migrate references."""
        if not merge_mappings:
            return

        for mapping in merge_mappings:
            points = await KnowledgeGraphRepository.list_points_by_target(
                db,
                user_id=user_id,
                target_id=target_id,
            )
            rows_by_key = {
                KnowledgeGraphRepository._normalize_point_name(point.name): point
                for point in points
            }
            source = rows_by_key.get(
                KnowledgeGraphRepository._normalize_point_name(
                    str(mapping.get("from_name", ""))
                )
            )
            target = rows_by_key.get(
                KnowledgeGraphRepository._normalize_point_name(
                    str(mapping.get("to_name", ""))
                )
            )
            if source is None or target is None or source.id == target.id:
                continue

            await KnowledgeGraphRepository._reparent_children(
                db,
                source=source,
                target=target,
            )
            await KnowledgeGraphRepository._merge_material_links(
                db,
                source_id=source.id,
                target_id=target.id,
            )
            await KnowledgeGraphRepository._merge_unique_point_links(
                db,
                model=QuestionKnowledgePoint,
                owner_column=QuestionKnowledgePoint.question_id,
                source_id=source.id,
                target_id=target.id,
            )
            await KnowledgeGraphRepository._merge_unique_point_links(
                db,
                model=WrongQuestionKnowledgePoint,
                owner_column=WrongQuestionKnowledgePoint.wrong_question_id,
                source_id=source.id,
                target_id=target.id,
            )
            await KnowledgeGraphRepository._merge_unique_point_links(
                db,
                model=QaKnowledgePoint,
                owner_column=QaKnowledgePoint.qa_record_id,
                source_id=source.id,
                target_id=target.id,
            )
            await KnowledgeGraphRepository._merge_review_plan_tasks(
                db,
                user_id=user_id,
                target_id=target_id,
                source_id=source.id,
                target_point_id=target.id,
            )
            await KnowledgeGraphRepository._merge_mastery_rows(
                db,
                user_id=user_id,
                target_id=target_id,
                source_id=source.id,
                target_point_id=target.id,
            )
            await db.flush()
            await db.delete(source)
            await db.flush()

        await db.commit()

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
