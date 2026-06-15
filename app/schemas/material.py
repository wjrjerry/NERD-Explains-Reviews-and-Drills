from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.material import MaterialParseStatus, MaterialType


class MaterialResponse(BaseModel):
    """资料信息响应模型。

    用于向前端返回资料元数据、解析状态和归属关系，不直接返回完整解析文本。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    target_id: int
    original_filename: str
    stored_filename: str
    file_type: MaterialType
    content_type: str | None
    file_size: int
    parse_status: MaterialParseStatus
    parse_error: str | None
    parse_warning: str | None = None
    created_at: datetime
    updated_at: datetime


class MaterialDetailResponse(BaseModel):
    """资料详情响应模型。"""

    material: MaterialResponse


class MaterialPreviewResponse(BaseModel):
    """资料预览响应模型。

    第一阶段预览优先返回 TXT 内容；PDF 和图片可先返回文件元数据或提示信息。
    """

    material: MaterialResponse
    preview_text: str | None
    message: str
