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

    预览保留原始 preview_text 兼容旧前端，并额外返回解析后的文本，
    供 TXT、PDF 和图片统一展示解析结果。
    """

    material: MaterialResponse
    preview_text: str | None
    parsed_text: str | None = None
    message: str
