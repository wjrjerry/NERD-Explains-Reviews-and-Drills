from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.parse_task import ParseTaskStatus, ParseTaskType


class ParseTaskResponse(BaseModel):
    """资料解析任务响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    user_id: int
    task_type: ParseTaskType
    task_status: ParseTaskStatus
    retry_count: int
    failure_reason: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ParseTaskDetailResponse(BaseModel):
    """资料解析任务详情响应模型。"""

    task: ParseTaskResponse
