"""Database models for AI knowledge extraction results."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeExtractionScope(str, PyEnum):
    """Knowledge extraction scope."""

    material = "material"
    target = "target"


class KnowledgeExtractionStatus(str, PyEnum):
    """Knowledge extraction execution status."""

    completed = "completed"
    failed = "failed"


class KnowledgeExtraction(Base):
    """AI-generated summary, outline, key points, and exam points.

    material scope stores a reading summary for one uploaded material.
    target scope stores an aggregated extraction for all parsed materials under
    one study target. The target-level extraction complements the graph tables:
    this table stores readable summary content, while knowledge_points stores
    the structured graph and mastery data.
    """

    __tablename__ = "knowledge_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="提炼结果所属用户ID",
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="目标级提炼所属课程/考试目标ID",
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="资料级提炼所属资料ID",
    )
    scope: Mapped[KnowledgeExtractionScope] = mapped_column(
        SqlEnum(KnowledgeExtractionScope, name="knowledge_extraction_scope"),
        index=True,
        nullable=False,
        comment="提炼范围：material 或 target",
    )
    status: Mapped[KnowledgeExtractionStatus] = mapped_column(
        SqlEnum(KnowledgeExtractionStatus, name="knowledge_extraction_status"),
        index=True,
        nullable=False,
        default=KnowledgeExtractionStatus.completed,
        comment="提炼状态",
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outline: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exam_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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
