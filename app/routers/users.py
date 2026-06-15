from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.user import CurrentUserResponse, UserResponse
from app.utils.responses import success

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息。

    该接口依赖 JWT 鉴权，前端需要在请求头中携带 Authorization: Bearer <token>。
    """
    return success(
        data=CurrentUserResponse(
            user=UserResponse.model_validate(current_user),
        )
    )