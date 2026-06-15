"""Database models for AI-generated quiz questions."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuestionType(str, PyEnum):
    """Supported question types."""

    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    subjective = "subjective"


class QuestionDifficulty(str, PyEnum):
    """Question difficulty levels used by generation and later scoring."""

    easy = "easy"
    medium = "medium"
    hard = "hard"


class Question(Base):
    """AI-generated question.

    The model stores generated questions so later test submission can load the
    correct answer and analysis by question_id. material_id is kept as an integer
    for now to reduce migration coupling with the materials module; user_id is
    protected by a real users foreign key for data isolation.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="题目自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="题目所属用户ID",
    )
    material_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="题目来源资料ID，后续可与 materials 表建立外键",
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_targets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="题目所属课程/考试目标ID；知识图谱出题时用于目标级归属",
    )
    question_type: Mapped[QuestionType] = mapped_column(
        SqlEnum(QuestionType, name="question_type"),
        index=True,
        nullable=False,
        comment="题型：单选、多选、判断或主观题",
    )
    stem: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="题干",
    )
    options: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="选项列表，主观题为空数组",
    )
    correct_answer: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="正确答案列表；主观题保存参考答案或评分要点",
    )
    analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="答案解析",
    )
    knowledge_points: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="题目关联知识点",
    )
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        SqlEnum(QuestionDifficulty, name="question_difficulty"),
        index=True,
        nullable=False,
        comment="题目难度",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="题目创建时间",
    )


class QuestionKnowledgePoint(Base):
    """Relation between generated questions and graph knowledge points."""

    __tablename__ = "question_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "knowledge_point_id",
            name="uq_question_knowledge_points_question_point",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="题目ID",
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="知识点ID",
    )
    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="题目与知识点的关联强度",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="关联创建时间",
    )
