from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_job import KnowledgeJob, KnowledgeJobStatus, KnowledgeJobType


class KnowledgeJobRepository:
    """Data access for asynchronous knowledge jobs."""

    @staticmethod
    def build_dedupe_key(
        *,
        user_id: int,
        job_type: KnowledgeJobType,
        target_id: int | None,
        material_id: int | None,
    ) -> str:
        if job_type == KnowledgeJobType.material_extract:
            return f"user:{user_id}:material:{material_id}:material_extract"
        if job_type == KnowledgeJobType.target_extract:
            return f"user:{user_id}:target:{target_id}:target_extract"
        if job_type == KnowledgeJobType.target_refresh_pipeline:
            return f"user:{user_id}:target:{target_id}:target_refresh_pipeline"
        if material_id is not None:
            return f"user:{user_id}:target:{target_id}:material:{material_id}:graph_refresh"
        return f"user:{user_id}:target:{target_id}:graph_refresh"

    @staticmethod
    async def get_by_id(db: AsyncSession, job_id: int) -> KnowledgeJob | None:
        result = await db.execute(select(KnowledgeJob).where(KnowledgeJob.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_dedupe_key(db: AsyncSession, dedupe_key: str) -> KnowledgeJob | None:
        result = await db.execute(select(KnowledgeJob).where(KnowledgeJob.dedupe_key == dedupe_key))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest(
        db: AsyncSession,
        *,
        user_id: int,
        job_type: KnowledgeJobType | None = None,
        target_id: int | None = None,
        material_id: int | None = None,
    ) -> KnowledgeJob | None:
        conditions = [KnowledgeJob.user_id == user_id]
        if job_type is not None:
            conditions.append(KnowledgeJob.job_type == job_type)
        if target_id is not None:
            conditions.append(KnowledgeJob.target_id == target_id)
        if material_id is not None:
            conditions.append(KnowledgeJob.material_id == material_id)

        result = await db.execute(
            select(KnowledgeJob)
            .where(*conditions)
            .order_by(KnowledgeJob.created_at.desc(), KnowledgeJob.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: int,
        job_type: KnowledgeJobType,
        target_id: int | None,
        material_id: int | None,
        force_regenerate: bool,
        max_points: int,
        dedupe_key: str,
    ) -> KnowledgeJob:
        job = KnowledgeJob(
            user_id=user_id,
            job_type=job_type,
            target_id=target_id,
            material_id=material_id,
            force_regenerate=force_regenerate,
            max_points=max_points,
            dedupe_key=dedupe_key,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def set_celery_task_id(
        db: AsyncSession,
        job: KnowledgeJob,
        *,
        celery_task_id: str | None,
    ) -> KnowledgeJob:
        job.celery_task_id = celery_task_id
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def request_rerun(db: AsyncSession, job: KnowledgeJob) -> KnowledgeJob:
        job.rerun_requested = True
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def reset_for_rerun(db: AsyncSession, job: KnowledgeJob) -> KnowledgeJob:
        job.status = KnowledgeJobStatus.pending
        job.rerun_requested = False
        job.error_message = None
        job.started_at = None
        job.finished_at = None
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_running(db: AsyncSession, job: KnowledgeJob) -> KnowledgeJob:
        job.status = KnowledgeJobStatus.running
        job.error_message = None
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = None
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_succeeded(db: AsyncSession, job: KnowledgeJob) -> KnowledgeJob:
        job.status = KnowledgeJobStatus.succeeded
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        job: KnowledgeJob,
        *,
        error_message: str,
    ) -> KnowledgeJob:
        job.status = KnowledgeJobStatus.failed
        job.error_message = error_message[:2000]
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job
