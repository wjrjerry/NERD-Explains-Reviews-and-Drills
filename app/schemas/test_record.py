from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestAnswerItem(BaseModel):
    question_id: int
    answer: list[str] = Field(
        default_factory=list,
        description="Objective answer keys, e.g. ['A'] or ['A', 'B'].",
    )
    answer_text: str | None = Field(
        default=None,
        description="Text answer for subjective questions.",
    )
    answer_file_ids: list[int] = Field(
        default_factory=list,
        description="Reserved file IDs for image/PDF answers after OCR is connected.",
    )
    answer_file_urls: list[str] = Field(
        default_factory=list,
        description="Reserved file URLs for image/PDF answers after OCR is connected.",
    )


class TestSubmitRequest(BaseModel):
    material_id: int = Field(description="Parsed material ID.")
    target_id: int | None = Field(default=None, description="Study target ID.")
    answers: list[TestAnswerItem]


class TestResultItem(BaseModel):
    question_id: int
    knowledge_point_ids: list[int] = Field(
        default_factory=list,
        description="Knowledge graph point IDs linked to this question.",
    )
    user_answer: list[str]
    correct_answer: list[str]
    is_correct: bool
    score: float = Field(description="Per-question score, from 0 to 1.")
    analysis: str
    matched_points: list[str] = Field(
        default_factory=list,
        description="Key points covered by the submitted answer.",
    )
    missing_points: list[str] = Field(
        default_factory=list,
        description="Expected key points missing from the submitted answer.",
    )
    misconceptions: list[str] = Field(
        default_factory=list,
        description="Conceptual mistakes found in the submitted answer.",
    )


class KnowledgePointTestSummary(BaseModel):
    knowledge_point_id: int
    total_count: int
    correct_count: int
    wrong_count: int
    accuracy: float
    average_score: float


class TestSubmitResponse(BaseModel):
    test_record_id: int
    score: float
    accuracy: float
    total_count: int
    correct_count: int
    wrong_count: int
    results: list[TestResultItem]
    knowledge_point_summary: list[KnowledgePointTestSummary] = Field(default_factory=list)


class TestRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    material_id: int
    target_id: int | None
    score: float
    accuracy: float
    total_count: int
    correct_count: int
    wrong_count: int
    created_at: datetime
