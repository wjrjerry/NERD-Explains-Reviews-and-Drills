from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    """用户数据访问仓储。

    负责封装 users 表的基础查询与写入操作，避免路由层直接操作 ORM。
    """

    @staticmethod
    # 异步处理，即等待数据库返回结果的期间，Python 进程可以处理其他前端请求
    async def get_by_username(db: AsyncSession, username: str) -> User | None:
        """根据用户名查询用户。"""
        # 异步等待
        result = await db.execute(
            select(User).where(
                User.username == username,
                User.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
        """根据用户 ID 查询未删除用户。

        后续解析 JWT 后，需要使用 token 中的用户 ID 重新查询数据库用户。
        """
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(
        db: AsyncSession,
        *,
        username: str,
        hashed_password: str,
        display_name: str | None,
        role: UserRole,
    ) -> User:
        """创建用户记录。"""
        user = User(
            username=username,
            hashed_password=hashed_password,
            display_name=display_name,
            role=role,
        )

        db.add(user) # user对象存入AsyncSession 的暂存区
        await db.commit() # 异步发起请求，落盘
        await db.refresh(user) # 落盘数据读回内存

        return user
    
    @staticmethod
    async def update_last_login_at(db: AsyncSession, user: User) -> User:
        """更新用户最后登录时间。

        该字段用于管理员后台查看用户最近活跃情况。
        """
        user.last_login_at = datetime.now(timezone.utc)

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user