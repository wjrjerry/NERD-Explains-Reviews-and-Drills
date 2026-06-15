from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminLogResponse(BaseModel):
    """管理员操作日志响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_user_id: int
    operation_type: str
    target_type: str
    target_id: int | None
    operation_result: str
    remark: str | None
    created_at: datetime
