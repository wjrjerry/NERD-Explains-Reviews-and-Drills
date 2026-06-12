from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudyTargetType(str, PyEnum):
    """课程/考试目标类型枚举类。"""

    course = "course"
    exam = "exam"


class StudyTarget(Base):
    """课程/考试目标核心数据模型。

    负责物理数据库 `study_targets` 表的 ORM 映射，用于承载学生创建的课程学习目标、
    考试备考目标以及后续资料、测试、错题和复习计划的数据归属。
    """

    __tablename__ = "study_targets"

    # --- 身份标识和归属关系 ---
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属用户ID，关联 users.id",
    )

    # --- 目标基础信息 ---
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="目标名称，例如数据库系统期末复习",
    )
    subject: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="课程或考试科目名称",
    )
    target_type: Mapped[StudyTargetType] = mapped_column(
        SqlEnum(StudyTargetType, name="study_target_type"),
        default=StudyTargetType.exam,
        nullable=False,
        comment="目标类型，course 表示课程目标，exam 表示考试目标",
    )
    exam_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="考试日期，可为空",
    )
    review_goal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="复习目标，例如掌握重点章节并完成错题复盘",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="目标备注说明，可为空",
    )

    # --- 状态控制 ---
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="软删除标记，True 表示该目标已删除",
    )

    # --- 业务审计与时间追踪 ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="记录创建时间，由数据库生成",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="记录最后更新时间，由 SQLAlchemy 在更新时刷新",
    )

    # --- ORM 关系 ---
    user = relationship(
        "User",
        backref="study_targets",
        lazy="selectin",
    )