from enum import StrEnum

from pydantic import BaseModel, Field


class QuestionType(StrEnum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    subjective = "subjective"


class QuestionDifficulty(StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class QuestionGenerateRequest(BaseModel):
    material_id: int = Field(description="Parsed material ID.")
    question_types: list[QuestionType] = Field(description="Question types to generate.")
    difficulty: QuestionDifficulty = Field(default=QuestionDifficulty.medium)
    count: int = Field(default=5, ge=1, le=50)


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
    difficulty: QuestionDifficulty


class QuestionGenerateResponse(BaseModel):
    material_id: int
    questions: list[QuestionItem]
