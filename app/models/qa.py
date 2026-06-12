"""Database models for material-based AI question-answer records."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QaRecord(Base):
    """一次“基于资料提问并由 AI 回答”的记录。

    这个模型对应数据库中的 qa_records 表，负责把用户在 /qa/ask 中
    提交的问题、AI 生成的回答、引用片段以及调用的模型信息保存下来。

    当前只对 user_id 建立外键，因为 users 表已经由认证模块稳定提供。
    material_id 暂时保留为普通整数，等待材料模块的 materials 表结构稳定后，
    再考虑补充真实外键约束。
    """

    __tablename__ = "qa_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        comment="问答记录自增主键ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="发起提问的用户ID",
    )
    material_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="本次问答所依据的资料ID，后续可与 materials 表建立外键",
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户提交的原始问题",
    )
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="AI 根据资料生成的回答",
    )
    references: Mapped[list[dict[str, int | str]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="回答引用的资料片段列表",
    )
    ai_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="生成回答时使用的 AI 提供方，例如 mock 或 openai-compatible",
    )
    ai_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="生成回答时使用的模型名，mock 模式下可为空",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="问答记录创建时间",
    )
