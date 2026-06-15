from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from app.schemas.response import ApiResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.utils.responses import fail, success

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[UserRegisterResponse])
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户注册接口。

    接收用户注册信息，完成用户名唯一性校验、密码哈希处理和用户入库。
    """
    try:
        user = await AuthService.register(db, payload)
    except ValueError as exc:
        return fail(code=40001, message=str(exc))

    return success(
        data=UserRegisterResponse(
            user=UserResponse.model_validate(user),
        )
    )

@router.post("/login", response_model=ApiResponse[UserLoginResponse])
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录接口。

    校验用户名和密码，登录成功后签发 JWT 访问令牌。
    """
    try:
        user, access_token = await AuthService.login(db, payload)
    except ValueError as exc:
        return fail(code=40002, message=str(exc))

    return success(
        data=UserLoginResponse(
            token=TokenResponse(access_token=access_token),
            user=UserResponse.model_validate(user),
        )
    )