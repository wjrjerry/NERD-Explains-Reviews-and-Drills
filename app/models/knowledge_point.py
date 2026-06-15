"""Database models for target-level knowledge graphs."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgePointSource(str, PyEnum):
    """How a knowledge point was created."""

    ai_generated = "ai_generated"
    manual = "manual"
    material_extracted = "material_extracted"


class MasteryStatus(str, PyEnum):
    """Current user mastery state for one knowledge point."""

    unlearned = "unlearned"
    weak = "weak"
    basic = "basic"
    proficient = "proficient"


class KnowledgePoint(Base):
    """One node in a study target's knowledge graph."""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[KnowledgePointSource] = mapped_column(
        SqlEnum(KnowledgePointSource, name="knowledge_point_source"),
        nullable=False,
        default=KnowledgePointSource.ai_generated,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MaterialKnowledgePoint(Base):
    """Evidence relation between one material and one knowledge point."""

    __tablename__ = "material_knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class UserKnowledgeMastery(Base):
    """A user's mastery state for one target-level knowledge point."""

    __tablename__ = "user_knowledge_mastery"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "target_id",
            "knowledge_point_id",
            name="uq_user_knowledge_mastery_user_target_point",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    mastery_status: Mapped[MasteryStatus] = mapped_column(
        SqlEnum(MasteryStatus, name="knowledge_mastery_status"),
        index=True,
        nullable=False,
        default=MasteryStatus.unlearned,
    )
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    answered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
