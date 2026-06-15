from pydantic import BaseModel, Field, model_validator

from app.schemas.knowledge_graph import KnowledgePointReference


class QaAskRequest(BaseModel):
    material_id: int | None = Field(default=None, description="Parsed material ID.")
    target_id: int | None = Field(
        default=None,
        description="Study target ID for target-level QA.",
    )
    knowledge_point_id: int | None = Field(
        default=None,
        description="Optional knowledge point ID for focused QA.",
    )
    question: str = Field(min_length=1, description="Question asked by the student.")

    @model_validator(mode="after")
    def validate_qa_scope(self) -> "QaAskRequest":
        """Require either material_id or target_id as the QA context."""
        if self.material_id is None and self.target_id is None:
            raise ValueError("material_id 或 target_id 至少需要提供一个")
        return self


class QaReference(BaseModel):
    material_id: int
    snippet: str


class QaAskResponse(BaseModel):
    qa_record_id: int
    material_id: int
    target_id: int | None = None
    question: str
    answer: str
    references: list[QaReference]
    knowledge_points: list[KnowledgePointReference] = Field(default_factory=list)
    created_at: str


class QaHistoryItem(BaseModel):
    """One saved QA record shown in the student's QA history."""

    qa_record_id: int
    material_id: int
    target_id: int | None = None
    question: str
    answer: str
    references: list[QaReference]
    knowledge_points: list[KnowledgePointReference] = Field(default_factory=list)
    ai_provider: str
    ai_model: str | None
    created_at: str
