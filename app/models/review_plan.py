"""Database models for review plans and daily review tasks."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewPlan(Base):
    """One generated review plan for a study target."""

    __tablename__ = "review_plans"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="复习计划自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="计划所属用户ID",
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="课程/考试目标ID",
    )
    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="复习计划标题",
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="计划开始日期",
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="计划结束日期",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="计划生成依据摘要",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="计划创建时间",
    )

    tasks = relationship(
        "ReviewPlanTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ReviewPlanTask.task_date.asc(), ReviewPlanTask.id.asc()",
    )


class ReviewPlanTask(Base):
    """One daily task under a review plan."""

    __tablename__ = "review_plan_tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="复习任务自增主键ID",
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("review_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属复习计划ID",
    )
    task_date: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
        comment="任务日期",
    )
    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="任务标题",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="任务内容",
    )
    material_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        comment="关联资料ID，可为空",
    )
    wrong_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("wrong_questions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="关联错题ID，可为空",
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="任务是否完成",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="任务创建时间",
    )

    plan = relationship("ReviewPlan", back_populates="tasks")
