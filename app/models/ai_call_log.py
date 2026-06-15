"""Database models for AI call monitoring and local billing."""

from datetime import datetime
from enum import Enum as PyEnum
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiCallStatus(str, PyEnum):
    """Provider call status recorded for observability and billing."""

    success = "success"
    failed = "failed"


class AiCallLog(Base):
    """One real AI provider call and its token-based local cost estimate."""

    __tablename__ = "ai_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="发起本次 AI 调用的用户ID",
    )
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_targets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="调用关联的课程/考试目标ID",
    )
    material_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        comment="调用关联的资料ID",
    )
    feature: Mapped[str] = mapped_column(
        String(80),
        index=True,
        nullable=False,
        comment="业务功能，例如 qa、question_generation、knowledge_graph_generation",
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[AiCallStatus] = mapped_column(
        SqlEnum(AiCallStatus, name="ai_call_status"),
        index=True,
        nullable=False,
    )
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_cache_hit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_cache_miss_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
        comment="按本平台本地 token 单价估算的费用",
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    billing_policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
