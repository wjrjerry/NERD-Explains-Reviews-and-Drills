from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.study_target import StudyTargetType


class StudyTargetCreateRequest(BaseModel):
    """课程/考试目标创建请求模型。"""

    title: str = Field(min_length=1, max_length=100, description="目标名称")
    subject: str | None = Field(default=None, max_length=100, description="课程或考试科目")
    target_type: StudyTargetType = Field(default=StudyTargetType.exam, description="目标类型")
    exam_date: date | None = Field(default=None, description="考试日期")
    review_goal: str | None = Field(default=None, description="复习目标")
    description: str | None = Field(default=None, description="备注说明")


class StudyTargetUpdateRequest(BaseModel):
    """课程/考试目标更新请求模型。

    所有字段均可选，便于 PATCH 接口进行局部更新。
    """

    title: str | None = Field(default=None, min_length=1, max_length=100, description="目标名称")
    subject: str | None = Field(default=None, max_length=100, description="课程或考试科目")
    target_type: StudyTargetType | None = Field(default=None, description="目标类型")
    exam_date: date | None = Field(default=None, description="考试日期")
    review_goal: str | None = Field(default=None, description="复习目标")
    description: str | None = Field(default=None, description="备注说明")


class StudyTargetResponse(BaseModel):
    """课程/考试目标响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    subject: str | None
    target_type: StudyTargetType
    exam_date: date | None
    review_goal: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class StudyTargetDetailResponse(BaseModel):
    """课程/考试目标详情响应模型。"""

    target: StudyTargetResponse