from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.material_structure import MaterialChunkType


class MaterialSectionResponse(BaseModel):
    """资料章节响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    parent_id: int | None
    title: str
    level: int
    order_index: int
    source_page: int | None
    created_at: datetime
    updated_at: datetime


class MaterialChunkResponse(BaseModel):
    """资料文本块响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    section_id: int | None
    chunk_type: MaterialChunkType
    title: str | None
    text: str
    order_index: int
    source_page: int | None
    created_at: datetime
    updated_at: datetime


class MaterialSectionsResponse(BaseModel):
    material_id: int
    sections: list[MaterialSectionResponse]


class MaterialChunksResponse(BaseModel):
    material_id: int
    chunks: list[MaterialChunkResponse]


class MaterialStructuredResponse(BaseModel):
    material_id: int
    sections: list[MaterialSectionResponse]
    chunks: list[MaterialChunkResponse]


class TargetChunksResponse(BaseModel):
    target_id: int
    chunks: list[MaterialChunkResponse]
