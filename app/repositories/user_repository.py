from datetime import datetime, timezone

from sqlalchemy import func, select
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
    async def list_users(
        db: AsyncSession,
        *,
        page: int,
        page_size: int,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        """分页查询未删除用户。

        管理员后台使用该方法查看系统用户，可按角色和启用状态筛选。
        """
        conditions = [User.is_deleted.is_(False)]

        if role is not None:
            conditions.append(User.role == role)

        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))

        total_result = await db.execute(
            select(func.count()).select_from(User).where(*conditions)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(result.scalars().all()), total

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
    async def update_active_status(db: AsyncSession, user: User, *, is_active: bool) -> User:
        """启用或禁用用户账号。"""
        user.is_active = is_active
        db.add(user)
        await db.commit()
        await db.refresh(user)
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
