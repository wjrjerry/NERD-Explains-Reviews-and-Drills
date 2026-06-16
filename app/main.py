from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.routers import (
    ai_usage,
    admin,
    auth,
    exports,
    health,
    knowledge,
    knowledge_graphs,
    knowledge_jobs,
    knowledge_points,
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
from app.services.bootstrap_service import BootstrapService
from app.utils.responses import success


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await BootstrapService.ensure_initial_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(ai_usage.router)
app.include_router(exports.router)
app.include_router(admin.router)
app.include_router(knowledge.router)
app.include_router(knowledge_graphs.router)
app.include_router(knowledge_jobs.router)
app.include_router(knowledge_points.router)
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
