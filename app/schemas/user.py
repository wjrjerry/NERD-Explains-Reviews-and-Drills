from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserResponse(BaseModel):
    """用户信息响应模型。

    用于向前端返回用户基础信息，不包含密码哈希等敏感字段。
    """

    # 允许从普通的 Python 对象属性中直接提取数据
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class CurrentUserResponse(BaseModel):
    """当前登录用户响应模型。

    用于 /users/me 接口，保持当前用户接口的响应结构稳定。
    """

    user: UserResponse