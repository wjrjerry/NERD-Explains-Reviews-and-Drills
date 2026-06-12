from pydantic import BaseModel, Field


class QaAskRequest(BaseModel):
    material_id: int = Field(description="Parsed material ID.")
    question: str = Field(min_length=1, description="Question asked by the student.")


class QaReference(BaseModel):
    material_id: int
    snippet: str


class QaAskResponse(BaseModel):
    qa_record_id: int
    question: str
    answer: str
    references: list[QaReference]
    created_at: str


class QaHistoryItem(BaseModel):
    """One saved QA record shown in the student's QA history."""

    qa_record_id: int
    material_id: int
    question: str
    answer: str
    references: list[QaReference]
    ai_provider: str
    ai_model: str | None
    created_at: str
