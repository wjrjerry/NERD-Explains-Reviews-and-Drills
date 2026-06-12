from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, create_access_token, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegisterRequest, UserLoginRequest


class AuthService:
    """认证服务。

    负责注册、登录和令牌签发等账号相关业务逻辑。
    """

    @staticmethod
    async def register(db: AsyncSession, payload: UserRegisterRequest) -> User:
        """注册新用户。

        注册流程：
        1. 校验用户名是否已存在。
        2. 对明文密码进行哈希处理。
        3. 创建用户记录并返回用户对象。
        """
        existing_user = await UserRepository.get_by_username(db, payload.username)
        if existing_user is not None:
            raise ValueError("用户名已存在")

        hashed_password = get_password_hash(payload.password)

        return await UserRepository.create_user(
            db,
            username=payload.username,
            hashed_password=hashed_password,
            display_name=payload.display_name,
            role=UserRole.student,
        )
    
    @staticmethod
    async def login(db: AsyncSession, payload: UserLoginRequest) -> tuple[User, str]:
        """用户登录。

        登录流程：
        1. 根据用户名查询用户。
        2. 校验账号状态和密码。
        3. 生成 JWT 访问令牌。
        4. 更新最后登录时间。
        """
        user = await UserRepository.get_by_username(db, payload.username)
        if user is None:
            raise ValueError("用户名或密码错误")

        if not user.is_active:
            raise ValueError("账号已被禁用")

        if not verify_password(payload.password, user.hashed_password):
            raise ValueError("用户名或密码错误")

        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={
                "role": user.role.value,
            },
        )

        user = await UserRepository.update_last_login_at(db, user)

        return user, access_token
