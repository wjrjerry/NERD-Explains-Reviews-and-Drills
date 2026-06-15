"""Knowledge mastery update service.

This module turns self-test answer results into target-level mastery data.
It is intentionally independent from question generation so later QA, wrong
question review, and tutor sessions can reuse the same update rules.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import MasteryStatus, UserKnowledgeMastery


@dataclass(frozen=True)
class KnowledgeMasteryAnswerOutcome:
    """One scored answer mapped to one or more knowledge points."""

    target_id: int
    knowledge_point_ids: list[int]
    is_correct: bool
    score: float


def calculate_mastery_status(*, answered_count: int, accuracy: float) -> MasteryStatus:
    """Map answer statistics to a student-facing mastery status."""
    if answered_count <= 0:
        return MasteryStatus.unlearned
    if accuracy < 0.6:
        return MasteryStatus.weak
    if accuracy < 0.85:
        return MasteryStatus.basic
    return MasteryStatus.proficient


def calculate_next_review_at(
    *,
    mastery_status: MasteryStatus,
    now: datetime,
) -> datetime:
    """Choose a simple spaced-review interval from the current mastery status."""
    if mastery_status == MasteryStatus.weak:
        return now + timedelta(days=1)
    if mastery_status == MasteryStatus.basic:
        return now + timedelta(days=3)
    if mastery_status == MasteryStatus.proficient:
        return now + timedelta(days=7)
    return now + timedelta(days=1)


async def update_mastery_after_test(
    db: AsyncSession,
    *,
    user_id: int,
    outcomes: list[KnowledgeMasteryAnswerOutcome],
) -> None:
    """Update user_knowledge_mastery after a submitted self-test.

    Each linked knowledge point receives one answered_count increment per
    question. Subjective partial scores are treated as correct only when the
    scoring step marked the answer as correct, while mastery_score keeps the
    resulting accuracy-like value for graph display.
    """
    if not outcomes:
        return

    point_ids = sorted(
        {
            point_id
            for outcome in outcomes
            for point_id in outcome.knowledge_point_ids
            if point_id > 0
        }
    )
    if not point_ids:
        return

    result = await db.execute(
        select(UserKnowledgeMastery).where(
            UserKnowledgeMastery.user_id == user_id,
            UserKnowledgeMastery.knowledge_point_id.in_(point_ids),
        )
    )
    mastery_by_point_id = {
        row.knowledge_point_id: row for row in result.scalars().all()
    }

    now = datetime.now(timezone.utc)
    for outcome in outcomes:
        for point_id in outcome.knowledge_point_ids:
            if point_id <= 0:
                continue

            row = mastery_by_point_id.get(point_id)
            if row is None:
                row = UserKnowledgeMastery(
                    user_id=user_id,
                    target_id=outcome.target_id,
                    knowledge_point_id=point_id,
                    mastery_status=MasteryStatus.unlearned,
                    mastery_score=0.0,
                    accuracy=0.0,
                    answered_count=0,
                    wrong_count=0,
                )
                db.add(row)
                mastery_by_point_id[point_id] = row

            row.answered_count += 1
            if not outcome.is_correct:
                row.wrong_count += 1

            correct_count = max(row.answered_count - row.wrong_count, 0)
            row.accuracy = round(correct_count / row.answered_count, 4)
            row.mastery_score = row.accuracy
            row.mastery_status = calculate_mastery_status(
                answered_count=row.answered_count,
                accuracy=row.accuracy,
            )
            row.last_practiced_at = now
            row.next_review_at = calculate_next_review_at(
                mastery_status=row.mastery_status,
                now=now,
            )

    await db.commit()
