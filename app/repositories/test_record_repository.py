from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_record import TestAnswerRecord, TestRecord


class TestRecordRepository:
    """Self-test submission data access layer."""

    @staticmethod
    async def create_test_record(
        db: AsyncSession,
        *,
        user_id: int,
        material_id: int,
        target_id: int | None,
        score: float,
        accuracy: float,
        total_count: int,
        correct_count: int,
        wrong_count: int,
        answer_details: list[dict[str, object]],
    ) -> tuple[TestRecord, list[TestAnswerRecord]]:
        """Insert one submitted test record and its per-question details."""
        record = TestRecord(
            user_id=user_id,
            material_id=material_id,
            target_id=target_id,
            score=score,
            accuracy=accuracy,
            total_count=total_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
        )

        db.add(record)
        await db.flush()

        answer_rows = [
            TestAnswerRecord(
                test_record_id=record.id,
                user_id=user_id,
                question_id=int(detail["question_id"]),
                user_answer=[
                    str(answer) for answer in detail["user_answer"]
                ],
                correct_answer=[
                    str(answer) for answer in detail["correct_answer"]
                ],
                is_correct=bool(detail["is_correct"]),
                score=float(detail["score"]),
                analysis=str(detail["analysis"]),
            )
            for detail in answer_details
        ]
        db.add_all(answer_rows)

        await db.commit()
        await db.refresh(record)
        for row in answer_rows:
            await db.refresh(row)

        return record, answer_rows

    @staticmethod
    async def get_test_record_by_id(
        db: AsyncSession,
        *,
        user_id: int,
        test_record_id: int,
    ) -> TestRecord | None:
        """Fetch one test record if it belongs to the current user."""
        result = await db.execute(
            select(TestRecord).where(
                TestRecord.id == test_record_id,
                TestRecord.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
