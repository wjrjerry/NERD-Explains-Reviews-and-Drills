from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.question import QuestionDifficulty, QuestionOption, QuestionType
from app.schemas.test_record import TestAnswerItem, TestResultItem


class MasteryStatus(str, Enum):
    unmastered = "unmastered"
    reviewing = "reviewing"
    mastered = "mastered"


class WrongQuestionResponse(BaseModel):
    id: int
    question_id: int
    target_id: int | None
    material_id: int
    stem: str
    user_answer: list[str]
    correct_answer: list[str]
    analysis: str
    wrong_reason: str
    knowledge_points: list[str]
    knowledge_point_ids: list[int] = Field(default_factory=list)
    mastery_status: MasteryStatus
    review_count: int = 0
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    question_type: QuestionType | None = None
    options: list[QuestionOption] = Field(default_factory=list)
    difficulty: QuestionDifficulty | None = None


class WrongQuestionMasteryUpdateRequest(BaseModel):
    mastery_status: MasteryStatus = Field(description="New mastery status.")


class WrongQuestionRedoRequest(BaseModel):
    answer: TestAnswerItem


class WrongQuestionRedoResponse(BaseModel):
    result: TestResultItem
    wrong_question: WrongQuestionResponse
