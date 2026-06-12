"""Database models for the wrong-question book."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MasteryStatus(str, PyEnum):
    """Wrong-question review mastery status."""

    unmastered = "unmastered"
    reviewing = "reviewing"
    mastered = "mastered"


class WrongQuestion(Base):
    """One wrong answer captured from a submitted self-test.

    The row stores a snapshot of the question and answers so the wrong-question
    book remains readable even if the original generated question is changed or
    deleted later.
    """

    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="错题记录自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="错题所属用户ID",
    )
    test_record_id: Mapped[int] = mapped_column(
        ForeignKey("test_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="来源自测记录ID",
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="来源题目ID",
    )
    target_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        comment="课程/考试目标ID，可为空",
    )
    material_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="来源资料ID",
    )
    stem: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="题干快照",
    )
    user_answer: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="用户错误答案",
    )
    correct_answer: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="正确答案",
    )
    analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="答案解析",
    )
    wrong_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="错误原因说明",
    )
    knowledge_points: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="关联知识点",
    )
    mastery_status: Mapped[MasteryStatus] = mapped_column(
        SqlEnum(MasteryStatus, name="mastery_status"),
        index=True,
        nullable=False,
        default=MasteryStatus.unmastered,
        comment="掌握状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="错题创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="错题更新时间",
    )
