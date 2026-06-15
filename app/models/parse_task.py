from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ParseTaskStatus(str, PyEnum):
    """资料解析任务状态。"""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ParseTaskType(str, PyEnum):
    """资料解析任务类型。"""

    material_parse = "material_parse"


class ParseTask(Base):
    """资料解析任务模型。

    该表用于追踪资料解析从排队、执行到成功或失败的完整生命周期。
    """

    __tablename__ = "parse_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联资料 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="资料所属用户 ID",
    )
    task_type: Mapped[ParseTaskType] = mapped_column(
        SqlEnum(ParseTaskType, name="parse_task_type"),
        default=ParseTaskType.material_parse,
        nullable=False,
        comment="任务类型",
    )
    task_status: Mapped[ParseTaskStatus] = mapped_column(
        SqlEnum(ParseTaskStatus, name="parse_task_status"),
        default=ParseTaskStatus.pending,
        nullable=False,
        index=True,
        comment="任务状态",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="重试次数",
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="失败原因",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始执行时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="执行结束时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    material = relationship("Material", lazy="selectin")
    user = relationship("User", lazy="selectin")
