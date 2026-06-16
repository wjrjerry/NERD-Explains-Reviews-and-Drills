from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "ai_study",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.parse_material_task": {"queue": "parse"},
        "app.tasks.process_knowledge_job_task": {"queue": "ai_target"},
    },
)
