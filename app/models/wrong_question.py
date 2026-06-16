"""Database models for the wrong-question book."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
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
    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="错题复习次数",
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次复习时间",
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="建议下次复习时间",
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


class WrongQuestionKnowledgePoint(Base):
    """Relation between one wrong question and graph knowledge points."""

    __tablename__ = "wrong_question_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "wrong_question_id",
            "knowledge_point_id",
            name="uq_wrong_question_knowledge_points_wrong_point",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wrong_question_id: Mapped[int] = mapped_column(
        ForeignKey("wrong_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="错题记录ID",
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="知识点ID",
    )
    wrong_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="该错题在该知识点上的错误原因",
    )
    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="错题与知识点的关联强度",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="关联创建时间",
    )
