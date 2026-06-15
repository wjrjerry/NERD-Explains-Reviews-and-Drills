from enum import Enum

from pydantic import BaseModel, Field, model_validator


class QuestionType(str, Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    subjective = "subjective"


class QuestionDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class QuestionGenerateRequest(BaseModel):
    material_id: int | None = Field(default=None, description="Parsed material ID.")
    target_id: int | None = Field(
        default=None,
        description="Study target ID. Required when generating by knowledge graph.",
    )
    knowledge_point_ids: list[int] = Field(
        default_factory=list,
        description="Optional knowledge point IDs under target_id. Empty means all points in the target graph.",
    )
    extra_requirement: str | None = Field(
        default=None,
        max_length=1000,
        description="Student-provided generation requirement, such as exam style, focus, or preferred scenario.",
    )
    question_types: list[QuestionType] = Field(description="Question types to generate.")
    difficulty: QuestionDifficulty = Field(default=QuestionDifficulty.medium)
    count: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def validate_generation_scope(self) -> "QuestionGenerateRequest":
        """Require either material_id or target_id so the backend knows the source scope."""
        if self.material_id is None and self.target_id is None:
            raise ValueError("material_id 或 target_id 至少需要提供一个")
        return self


class QuestionOption(BaseModel):
    key: str
    text: str
    analysis: str = Field(
        default="",
        description="Explanation for why this option is correct or incorrect.",
    )


class QuestionItem(BaseModel):
    id: int
    type: QuestionType
    stem: str
    options: list[QuestionOption]
    correct_answer: list[str]
    analysis: str
    knowledge_points: list[str]
    knowledge_point_ids: list[int] = Field(default_factory=list)
    difficulty: QuestionDifficulty


class QuestionGenerateResponse(BaseModel):
    material_id: int | None = None
    target_id: int | None = None
    questions: list[QuestionItem]
