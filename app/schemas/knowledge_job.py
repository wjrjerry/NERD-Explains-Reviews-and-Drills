from datetime import datetime

from pydantic import BaseModel, Field

from app.models.knowledge_job import KnowledgeJobStatus, KnowledgeJobType


class KnowledgeJobResponse(BaseModel):
    id: int
    job_type: KnowledgeJobType
    status: KnowledgeJobStatus
    target_id: int | None
    material_id: int | None
    force_regenerate: bool
    max_points: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class MaterialExtractJobRequest(BaseModel):
    material_id: int


class TargetExtractJobRequest(BaseModel):
    target_id: int
    force_regenerate: bool = True


class GraphRefreshJobRequest(BaseModel):
    target_id: int
    material_id: int | None = None
    force_regenerate: bool = True
    max_points: int = Field(default=12, ge=1, le=30)
