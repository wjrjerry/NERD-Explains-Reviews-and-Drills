from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaterialChunkType(str, PyEnum):
    """结构化文本块类型。"""

    text = "text"
    definition = "definition"
    formula = "formula"
    example = "example"
    key_sentence = "key_sentence"


class MaterialSection(Base):
    """资料章节/小节结构。"""

    __tablename__ = "material_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="关联资料 ID",
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_sections.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="父章节 ID",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="章节标题")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="章节层级")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="排序序号")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="来源页码")
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

    material = relationship("Material", backref="sections", lazy="selectin")


class MaterialChunk(Base):
    """可供 AI 检索和生成使用的资料文本块。"""

    __tablename__ = "material_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="关联资料 ID",
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_sections.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="关联章节 ID",
    )
    chunk_type: Mapped[MaterialChunkType] = mapped_column(
        SqlEnum(MaterialChunkType, name="material_chunk_type"),
        default=MaterialChunkType.text,
        nullable=False,
        index=True,
        comment="文本块类型",
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="文本块标题")
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="文本块内容")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="排序序号")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="来源页码")
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

    material = relationship("Material", backref="chunks", lazy="selectin")
    section = relationship("MaterialSection", backref="chunks", lazy="selectin")
