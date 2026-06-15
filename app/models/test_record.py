"""Database models for quiz submissions and scoring results."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TestRecord(Base):
    """One submitted self-test summary.

    A test record stores the aggregate score for one submission. Per-question
    details are stored in TestAnswerRecord so later wrong-question and review
    modules can reuse the same scoring results.
    """

    __tablename__ = "test_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="自测记录自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="提交自测的用户ID",
    )
    material_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="自测来源资料ID",
    )
    target_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        comment="课程/考试目标ID，可为空",
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="百分制得分",
    )
    accuracy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="正确率，取值范围 0 到 1",
    )
    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="提交题目总数",
    )
    correct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="答对题目数",
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="答错题目数",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="提交时间",
    )


class TestAnswerRecord(Base):
    """Per-question scoring detail for one submitted self-test."""

    __tablename__ = "test_answer_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="作答记录自增主键ID",
    )
    test_record_id: Mapped[int] = mapped_column(
        ForeignKey("test_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属自测记录ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="作答用户ID",
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="题目ID",
    )
    user_answer: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="用户提交答案",
    )
    correct_answer: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="正确答案",
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="是否答对",
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        comment="单题得分，取值范围 0 到 1",
    )
    analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="答案解析",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="作答记录创建时间",
    )
