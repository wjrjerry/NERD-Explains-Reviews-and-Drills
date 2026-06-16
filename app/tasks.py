import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

from app.celery_app import celery_app

_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_lock = threading.Lock()


def _run_in_worker_loop(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run coroutines on one stable loop per worker process.

    SQLAlchemy asyncpg connections are tied to the event loop that created them.
    Reusing a pooled connection across repeated asyncio.run() calls can attach
    asyncpg futures to the wrong loop inside a long-lived Celery worker.
    """
    global _worker_loop
    with _worker_loop_lock:
        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
        return _worker_loop.run_until_complete(coro)


def _run_in_fresh_loop(coro: Coroutine[Any, Any, Any]) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run async service code from a Celery task, including eager ASGI tests."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_in_worker_loop(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = _run_in_fresh_loop(coro)
        except BaseException as exc:  # pragma: no cover - re-raised below
            result["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


@celery_app.task(name="app.tasks.parse_material_task")
def parse_material_task(task_id: int) -> None:
    from app.services.parser_service import ParserService

    _run_async(ParserService.parse_material_by_task_id(task_id))


@celery_app.task(name="app.tasks.process_knowledge_job_task")
def process_knowledge_job_task(job_id: int) -> None:
    from app.services.knowledge_job_service import KnowledgeJobService

    _run_async(KnowledgeJobService.process_job_by_id(job_id))
