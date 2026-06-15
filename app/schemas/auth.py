from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class UserRegisterRequest(BaseModel):
    """用户注册请求模型。

    仅接收创建账号所需的最小字段，密码会在服务层完成哈希处理后再入库。
    """

    username: str = Field(min_length=3, max_length=50, description="唯一用户名")
    password: str = Field(min_length=6, max_length=72, description="登录密码明文，仅用于注册请求")
    display_name: str | None = Field(default=None, max_length=50, description="用户昵称")


class UserRegisterResponse(BaseModel):
    """用户注册响应模型。"""

    user: UserResponse


class UserLoginRequest(BaseModel):
    """用户登录请求模型。

    接收用户名和明文密码，实际密码校验在服务层完成。
    """

    username: str = Field(min_length=3, max_length=50, description="唯一用户名")
    password: str = Field(min_length=6, max_length=72, description="登录密码明文，仅用于登录请求")


class TokenResponse(BaseModel):
    """登录令牌响应模型。

    access_token 用于后续请求的 Authorization 请求头，token_type 固定为 Bearer。
    """

    access_token: str
    token_type: str = "bearer"


class UserLoginResponse(BaseModel):
    """用户登录响应模型。

    登录成功后同时返回访问令牌和当前用户基础信息。
    """

    token: TokenResponse
    user: UserResponse
