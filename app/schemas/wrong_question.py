from enum import Enum

from pydantic import BaseModel, Field


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


class WrongQuestionMasteryUpdateRequest(BaseModel):
    mastery_status: MasteryStatus = Field(description="New mastery status.")
