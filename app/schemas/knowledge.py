"""Pydantic schemas for the unified AI knowledge extraction API."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.schemas.knowledge_graph import KnowledgeGraphResponse


class KnowledgeExtractionScope(StrEnum):
    material = "material"
    target = "target"


class KnowledgeExtractRequest(BaseModel):
    """Request body for starting knowledge extraction.

    material_id starts material-level extraction for one parsed material.
    target_id starts target-level extraction for all parsed materials under one
    study target and also refreshes the target-level knowledge graph.
    """

    material_id: int | None = Field(default=None, description="Parsed material ID.")
    target_id: int | None = Field(default=None, description="Study target ID.")
    force_regenerate: bool = Field(
        default=False,
        description="Regenerate target-level extraction and graph even when existing data is present.",
    )

    @model_validator(mode="after")
    def validate_scope(self) -> "KnowledgeExtractRequest":
        """Require exactly one extraction scope."""
        if self.material_id is None and self.target_id is None:
            raise ValueError("material_id 或 target_id 至少需要提供一个")
        if self.material_id is not None and self.target_id is not None:
            raise ValueError("material_id 和 target_id 不能同时提供")
        return self


class KnowledgeExtractResponse(BaseModel):
    """Response body returned after material-level or target-level extraction."""

    extraction_id: int | None = None
    scope: KnowledgeExtractionScope
    material_id: int | None = None
    target_id: int | None = None
    summary: str
    outline: list[str]
    keywords: list[str]
    key_points: list[str]
    exam_points: list[str]
    knowledge_graph: KnowledgeGraphResponse | None = None
