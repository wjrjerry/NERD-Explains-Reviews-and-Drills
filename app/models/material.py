from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MaterialType(str, PyEnum):
    """资料文件类型枚举类。"""

    pdf = "pdf"
    txt = "txt"
    image = "image"


class MaterialParseStatus(str, PyEnum):
    """资料解析状态枚举类。"""

    uploaded = "uploaded"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


class Material(Base):
    """资料核心数据模型。

    负责物理数据库 `materials` 表的 ORM 映射，用于保存学生上传的 PDF、TXT、
    图片资料元数据、存储路径和后续解析状态。
    """

    __tablename__ = "materials"

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
    target_id: Mapped[int] = mapped_column(
        ForeignKey("study_targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属课程/考试目标ID，关联 study_targets.id",
    )

    # --- 文件基础信息 ---
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用户上传时的原始文件名",
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="服务端保存时生成的唯一文件名",
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="服务端文件存储路径",
    )
    file_type: Mapped[MaterialType] = mapped_column(
        SqlEnum(MaterialType, name="material_type"),
        nullable=False,
        comment="资料文件类型，支持 pdf、txt、image",
    )
    content_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="上传文件的 MIME 类型",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="文件大小，单位字节",
    )

    # --- 解析状态和文本内容 ---
    parse_status: Mapped[MaterialParseStatus] = mapped_column(
        SqlEnum(MaterialParseStatus, name="material_parse_status"),
        default=MaterialParseStatus.uploaded,
        nullable=False,
        index=True,
        comment="资料解析状态",
    )
    parsed_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="资料解析后的文本内容",
    )
    parse_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="资料解析失败原因",
    )

    # --- 状态控制 ---
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="软删除标记，True 表示该资料已删除",
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
        backref="materials",
        lazy="selectin",
    )
    target = relationship(
        "StudyTarget",
        backref="materials",
        lazy="selectin",
    )