"""Pydantic schemas for the AI knowledge extraction API.

Schemas describe the shape of API input/output. They are not database tables.
The frontend and backend should both treat these fields as the contract for
POST /knowledge/extract.
"""

from pydantic import BaseModel, Field


class KnowledgeExtractRequest(BaseModel):
    """Request body for starting knowledge extraction.

    material_id:
        The uploaded material to analyze. This material must already be parsed.

    target_id:
        Optional course/exam target. Keeping it optional lets the first version
        work even if target association is not finished yet.
    """

    material_id: int = Field(description="Parsed material ID.")
    target_id: int | None = Field(default=None, description="Study target ID.")


class KnowledgeExtractResponse(BaseModel):
    """Response body returned after knowledge extraction.

    These fields are designed for the "资料详情与 AI 学习页":
    - summary: short overview of the material.
    - outline: chapter or section structure.
    - keywords: important terms.
    - key_points: concepts the student should understand.
    - exam_points: likely exam/review focus points.
    """

    material_id: int
    summary: str
    outline: list[str]
    keywords: list[str]
    key_points: list[str]
    exam_points: list[str]
