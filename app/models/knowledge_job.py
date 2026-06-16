from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeJobType(str, PyEnum):
    """AI knowledge task type."""

    material_extract = "material_extract"
    target_extract = "target_extract"
    graph_refresh = "graph_refresh"
    target_refresh_pipeline = "target_refresh_pipeline"


class KnowledgeJobStatus(str, PyEnum):
    """AI knowledge task lifecycle status."""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class KnowledgeJob(Base):
    """Persistent status row for asynchronous knowledge and graph jobs."""

    __tablename__ = "knowledge_jobs"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_knowledge_jobs_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[KnowledgeJobType] = mapped_column(
        SqlEnum(KnowledgeJobType, name="knowledge_job_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[KnowledgeJobStatus] = mapped_column(
        SqlEnum(KnowledgeJobStatus, name="knowledge_job_status"),
        default=KnowledgeJobStatus.pending,
        nullable=False,
        index=True,
    )
    force_regenerate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    rerun_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
