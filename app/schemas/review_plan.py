from datetime import date

from pydantic import BaseModel, Field


class ReviewPlanGenerateRequest(BaseModel):
    target_id: int = Field(description="Study target ID.")
    start_date: date | None = Field(default=None, description="Plan start date.")
    end_date: date | None = Field(default=None, description="Plan end date.")


class ReviewPlanTask(BaseModel):
    id: int
    date: date
    title: str
    content: str
    material_id: int | None = None
    wrong_question_id: int | None = None
    knowledge_point_id: int | None = None
    completed: bool = False


class ReviewPlanResponse(BaseModel):
    id: int
    target_id: int
    title: str
    start_date: date
    end_date: date
    summary: str
    tasks: list[ReviewPlanTask]
