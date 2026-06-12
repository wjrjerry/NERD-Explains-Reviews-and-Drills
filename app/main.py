from fastapi import FastAPI

from app.core.config import settings
from app.routers import (
    auth,
    health,
    knowledge,
    materials,
    qa,
    questions,
    review_plans,
    study_targets,
    tests,
    users,
    wrong_questions,
)
from app.schemas.response import ApiResponse
from app.utils.responses import success

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(knowledge.router)
app.include_router(qa.router)
app.include_router(questions.router)
app.include_router(tests.router)
app.include_router(wrong_questions.router)
app.include_router(review_plans.router)
app.include_router(study_targets.router)
app.include_router(materials.router)


@app.get("/", response_model=ApiResponse[dict[str, str]])
def root():
    return success(
        {
            "message": "backend is running",
            "app_name": settings.app_name,
            "env": settings.app_env,
        }
    )
