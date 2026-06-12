from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, PyEnum):
    """用户核心权限角色枚举类"""
    student = "student"
    admin = "admin"


class User(Base):
    """用户系统核心数据模型
    负责物理数据库`users`表的ORM映射，以及账户生命周期管理、鉴权凭证和审计追踪
    """
    __tablename__ = "users"
    
    # --- 身份标识和认证凭证--- 
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        index=True,
        comment="自增主键ID"
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="唯一个体用户名"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), 
        nullable=False
    )

    # --- 基础属性和权限分级 ---
    display_name: Mapped[str | None] = mapped_column(
        String(50), 
        nullable=True,
        comment="用户昵称，可空"
    )

    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role"),
        default=UserRole.student,
        nullable=False,
        comment="系统权限角色，默认指定为student"
    )

    # --- 状态控制（生命周期状态机） ---
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False,
        comment="账户激活状态，False表示账户被封"    
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False,
        comment = "更新该字段为True即视作删除"    
    )

    # --- 业务审计与时间追踪 ---
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后完成鉴权登录的带时区时间戳"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="记录创建时间，由持久层数据库内核生成"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="记录最终修改时间，每当该用户的任意其他字段被更新并触发 UPDATE 语句提交时，SQLAlchemy 引擎会自动将该值强行刷新为当前最新时间"
    )
