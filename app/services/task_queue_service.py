from app.tasks import parse_material_task, process_knowledge_job_task


class TaskQueueService:
    """Small wrapper around Celery dispatch so routers stay framework-light."""

    @staticmethod
    def enqueue_parse_task(task_id: int) -> str | None:
        result = parse_material_task.apply_async(args=[task_id], queue="parse")
        return result.id

    @staticmethod
    def enqueue_knowledge_job(job_id: int, *, queue: str) -> str | None:
        result = process_knowledge_job_task.apply_async(args=[job_id], queue=queue)
        return result.id
