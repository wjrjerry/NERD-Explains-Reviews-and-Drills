from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AdminLog(Base):
    """管理员操作日志模型。"""

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="执行操作的管理员用户 ID",
    )
    operation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="操作类型，例如 retry_parse",
    )
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="操作对象类型，例如 material 或 parse_task",
    )
    target_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="操作对象 ID",
    )
    operation_result: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="操作结果，例如 success 或 failed",
    )
    remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="备注信息",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="日志创建时间",
    )

    admin_user = relationship("User", lazy="selectin")
