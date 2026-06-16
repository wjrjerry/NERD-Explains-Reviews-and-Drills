from sqlalchemy.ext.asyncio import AsyncSession

import app.db.session as db_session
from app.models.knowledge_job import KnowledgeJob, KnowledgeJobStatus, KnowledgeJobType
from app.models.material import MaterialParseStatus
from app.models.user import User
from app.repositories.knowledge_job_repository import KnowledgeJobRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.knowledge import KnowledgeExtractRequest
from app.schemas.knowledge_graph import KnowledgeGraphGenerateRequest
from app.services import knowledge_service
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.task_queue_service import TaskQueueService


def _job_queue(job_type: KnowledgeJobType) -> str:
    return "ai_material" if job_type == KnowledgeJobType.material_extract else "ai_target"


class KnowledgeJobService:
    """Orchestrates asynchronous knowledge extraction and graph refresh jobs."""

    @staticmethod
    async def enqueue(
        db: AsyncSession,
        *,
        current_user: User,
        job_type: KnowledgeJobType,
        target_id: int | None,
        material_id: int | None,
        force_regenerate: bool = True,
        max_points: int = 12,
    ) -> KnowledgeJob:
        dedupe_key = KnowledgeJobRepository.build_dedupe_key(
            user_id=current_user.id,
            job_type=job_type,
            target_id=target_id,
            material_id=material_id,
        )
        existing = await KnowledgeJobRepository.get_by_dedupe_key(db, dedupe_key)
        if existing is not None:
            existing.force_regenerate = force_regenerate
            existing.max_points = max_points
            if existing.status == KnowledgeJobStatus.pending:
                db.add(existing)
                await db.commit()
                await db.refresh(existing)
                return existing
            if existing.status == KnowledgeJobStatus.running:
                return await KnowledgeJobRepository.request_rerun(db, existing)
            job = await KnowledgeJobRepository.reset_for_rerun(db, existing)
        else:
            job = await KnowledgeJobRepository.create(
                db,
                user_id=current_user.id,
                job_type=job_type,
                target_id=target_id,
                material_id=material_id,
                force_regenerate=force_regenerate,
                max_points=max_points,
                dedupe_key=dedupe_key,
            )

        celery_task_id = TaskQueueService.enqueue_knowledge_job(job.id, queue=_job_queue(job_type))
        return await KnowledgeJobRepository.set_celery_task_id(
            db,
            job,
            celery_task_id=celery_task_id,
        )

    @staticmethod
    async def enqueue_material_extract(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> KnowledgeJob:
        material = await MaterialRepository.get_by_id(
            db,
            material_id=material_id,
            user_id=current_user.id,
        )
        if material is None:
            raise ValueError("资料不存在")
        if material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
            raise ValueError("资料未解析完成")
        return await KnowledgeJobService.enqueue(
            db,
            current_user=current_user,
            job_type=KnowledgeJobType.material_extract,
            target_id=material.target_id,
            material_id=material.id,
            force_regenerate=True,
            max_points=12,
        )

    @staticmethod
    async def enqueue_target_extract(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
        force_regenerate: bool,
    ) -> KnowledgeJob:
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")
        return await KnowledgeJobService.enqueue(
            db,
            current_user=current_user,
            job_type=KnowledgeJobType.target_extract,
            target_id=target_id,
            material_id=None,
            force_regenerate=force_regenerate,
            max_points=12,
        )

    @staticmethod
    async def enqueue_graph_refresh(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
        material_id: int | None,
        force_regenerate: bool,
        max_points: int,
        job_type: KnowledgeJobType = KnowledgeJobType.graph_refresh,
    ) -> KnowledgeJob:
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")

        if material_id is not None:
            material = await MaterialRepository.get_by_id(
                db,
                material_id=material_id,
                user_id=current_user.id,
            )
            if material is None or material.target_id != target_id:
                raise ValueError("资料不存在或不属于当前目标")
            if material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
                raise ValueError("资料未解析完成")

        return await KnowledgeJobService.enqueue(
            db,
            current_user=current_user,
            job_type=job_type,
            target_id=target_id,
            material_id=material_id,
            force_regenerate=force_regenerate,
            max_points=max_points,
        )

    @staticmethod
    async def enqueue_after_material_parsed(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> None:
        material = await MaterialRepository.get_by_id(
            db,
            material_id=material_id,
            user_id=current_user.id,
        )
        if material is None or material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
            return
        await KnowledgeJobService.enqueue_material_extract(
            db,
            current_user=current_user,
            material_id=material.id,
        )
        await KnowledgeJobService.enqueue_graph_refresh(
            db,
            current_user=current_user,
            target_id=material.target_id,
            material_id=None,
            force_regenerate=True,
            max_points=30,
            job_type=KnowledgeJobType.target_refresh_pipeline,
        )

    @staticmethod
    async def process_job_by_id(job_id: int) -> None:
        async with db_session.AsyncSessionLocal() as db:
            job = await KnowledgeJobRepository.get_by_id(db, job_id)
            if job is None:
                return
            if job.status == KnowledgeJobStatus.running:
                return

            job = await KnowledgeJobRepository.mark_running(db, job)
            try:
                await KnowledgeJobService._run_job(db, job)
            except Exception as exc:
                await db.rollback()
                job = await KnowledgeJobRepository.get_by_id(db, job_id)
                if job is not None:
                    await KnowledgeJobRepository.mark_failed(
                        db,
                        job,
                        error_message=str(exc) or "知识任务执行失败",
                    )
                return

            rerun_requested = job.rerun_requested
            job = await KnowledgeJobRepository.mark_succeeded(db, job)
            if rerun_requested:
                job = await KnowledgeJobRepository.reset_for_rerun(db, job)
                celery_task_id = TaskQueueService.enqueue_knowledge_job(
                    job.id,
                    queue=_job_queue(job.job_type),
                )
                await KnowledgeJobRepository.set_celery_task_id(
                    db,
                    job,
                    celery_task_id=celery_task_id,
                )

    @staticmethod
    async def _run_job(db: AsyncSession, job: KnowledgeJob) -> None:
        user = User(id=job.user_id)
        if job.job_type == KnowledgeJobType.material_extract:
            if job.material_id is None:
                raise ValueError("资料级知识任务缺少 material_id")
            payload = KnowledgeExtractRequest(material_id=job.material_id)
            await knowledge_service.extract_knowledge(db, payload, current_user=user)
            return

        if job.job_type == KnowledgeJobType.target_extract:
            if job.target_id is None:
                raise ValueError("目标级知识任务缺少 target_id")
            await knowledge_service.extract_target_summary(
                db,
                current_user=user,
                target_id=job.target_id,
                force_regenerate=job.force_regenerate,
            )
            return

        if job.job_type == KnowledgeJobType.target_refresh_pipeline:
            if job.material_id is not None:
                payload = KnowledgeExtractRequest(material_id=job.material_id)
                await knowledge_service.extract_knowledge(db, payload, current_user=user)
            if job.target_id is None:
                raise ValueError("目标刷新任务缺少 target_id")
            await knowledge_service.extract_target_summary(
                db,
                current_user=user,
                target_id=job.target_id,
                force_regenerate=False,
            )
            await KnowledgeGraphService.generate(
                db,
                current_user=user,
                payload=KnowledgeGraphGenerateRequest(
                    target_id=job.target_id,
                    material_id=job.material_id,
                    force_regenerate=True,
                    max_points=job.max_points,
                ),
            )
            return

        if job.job_type == KnowledgeJobType.graph_refresh:
            if job.target_id is None:
                raise ValueError("图谱刷新任务缺少 target_id")
            await KnowledgeGraphService.generate(
                db,
                current_user=user,
                payload=KnowledgeGraphGenerateRequest(
                    target_id=job.target_id,
                    material_id=job.material_id,
                    force_regenerate=job.force_regenerate,
                    max_points=job.max_points,
                ),
            )
            return

        raise ValueError("不支持的知识任务类型")
