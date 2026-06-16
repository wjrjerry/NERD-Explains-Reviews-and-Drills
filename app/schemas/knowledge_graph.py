"""Schemas for target-level knowledge graph APIs."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.knowledge_point import MasteryStatus


class KnowledgeGraphGenerateRequest(BaseModel):
    """Request body for generating a target-level knowledge graph."""

    target_id: int = Field(description="Study target ID.")
    material_id: int | None = Field(
        default=None,
        description="Optional parsed material ID for incremental graph refresh.",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Replace existing graph if one already exists.",
    )
    max_points: int = Field(default=12, ge=1, le=30, description="Maximum graph nodes updated per run.")


class KnowledgePointReference(BaseModel):
    """Small knowledge point summary embedded by other modules."""

    id: int
    name: str
    importance_weight: float


class KnowledgePointMaterialReference(BaseModel):
    """Material evidence supporting one knowledge point."""

    material_id: int
    evidence_text: str | None = None
    relevance_score: float


class KnowledgePointNode(BaseModel):
    """One node returned to the frontend for graph visualization."""

    id: int
    parent_id: int | None
    name: str
    description: str | None
    importance_weight: float
    level: int
    sort_order: int
    mastery_status: MasteryStatus
    mastery_score: float
    accuracy: float
    answered_count: int
    wrong_count: int
    materials: list[KnowledgePointMaterialReference] = Field(default_factory=list)


class KnowledgeGraphResponse(BaseModel):
    """Target-level knowledge graph response."""

    target_id: int
    nodes: list[KnowledgePointNode]
    generated_at: datetime | None = None


class KnowledgePointMasteryUpdateRequest(BaseModel):
    """Request body for manually adjusting one knowledge point mastery state."""

    mastery_status: MasteryStatus | None = Field(
        default=None,
        description="Manual mastery status. If omitted, only numeric fields are updated.",
    )
    mastery_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Manual mastery score from 0 to 1.",
    )
    next_review_at: datetime | None = Field(
        default=None,
        description="Optional next review time for this knowledge point.",
    )


class KnowledgePointMasteryResponse(BaseModel):
    """Mastery row returned after manual or automatic update."""

    knowledge_point_id: int
    target_id: int
    mastery_status: MasteryStatus
    mastery_score: float
    accuracy: float
    answered_count: int
    wrong_count: int
    last_practiced_at: datetime | None
    next_review_at: datetime | None


class KnowledgePointMaterialItem(BaseModel):
    """Material evidence item for one knowledge point."""

    material_id: int
    target_id: int
    original_filename: str
    file_type: str
    parse_status: str
    evidence_text: str | None
    relevance_score: float


class KnowledgePointMaterialsResponse(BaseModel):
    """Materials and snippets that support one knowledge point."""

    knowledge_point_id: int
    items: list[KnowledgePointMaterialItem]
