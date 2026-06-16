"""Business service for unified material/target knowledge extraction."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeExtraction, KnowledgeExtractionScope as ModelScope
from app.models.material import Material, MaterialParseStatus
from app.models.user import User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.knowledge import (
    KnowledgeExtractRequest,
    KnowledgeExtractionScope,
    KnowledgeExtractResponse,
)
from app.schemas.knowledge_graph import KnowledgeGraphGenerateRequest, KnowledgeGraphResponse
from app.services import ai_service, ai_usage_service
from app.services.knowledge_graph_service import KnowledgeGraphService


def _normalize_string_list(value: object) -> list[str]:
    """Normalize AI-returned list-like fields to list[str]."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _to_response(
    row: KnowledgeExtraction,
    *,
    knowledge_graph: KnowledgeGraphResponse | None = None,
) -> KnowledgeExtractResponse:
    """Map a stored extraction row to the public response schema."""
    return KnowledgeExtractResponse(
        extraction_id=row.id,
        scope=KnowledgeExtractionScope(row.scope.value),
        material_id=row.material_id,
        target_id=row.target_id,
        summary=row.summary,
        outline=[str(item) for item in row.outline],
        keywords=[str(item) for item in row.keywords],
        key_points=[str(item) for item in row.key_points],
        exam_points=[str(item) for item in row.exam_points],
        knowledge_graph=knowledge_graph,
    )


def _materials_for_knowledge(materials: list[Material]) -> list[dict[str, object]]:
    """Build structured target-level extraction input from parsed materials."""
    blocks: list[dict[str, object]] = []
    for material in materials:
        parsed_text = (material.parsed_text or "").strip()
        if not parsed_text:
            continue
        blocks.append(
            {
                "material_id": material.id,
                "title": material.original_filename,
                "content": parsed_text,
            }
        )
    return blocks


async def extract_material_knowledge(
    db: AsyncSession,
    *,
    current_user: User,
    material: Material,
) -> KnowledgeExtractResponse:
    """Generate and save material-level extraction for one parsed material."""
    if material.user_id != current_user.id:
        raise ValueError("资料不存在")
    if material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
        raise ValueError("资料未解析完成")

    ai_usage_service.clear_pending_traces()
    try:
        generated = ai_service.generate_knowledge(
            material.parsed_text,
            target_name=material.original_filename,
            scope="material",
            source_materials=[
                {
                    "material_id": material.id,
                    "title": material.original_filename,
                    "content": material.parsed_text,
                }
            ],
        )
    finally:
        await ai_usage_service.record_pending_traces(
            db,
            user_id=current_user.id,
            target_id=material.target_id,
            material_id=material.id,
        )
    row = await KnowledgeRepository.save_extraction(
        db,
        user_id=current_user.id,
        scope=ModelScope.material,
        target_id=material.target_id,
        material_id=material.id,
        summary=str(generated["summary"]),
        outline=_normalize_string_list(generated["outline"]),
        keywords=_normalize_string_list(generated["keywords"]),
        key_points=_normalize_string_list(generated["key_points"]),
        exam_points=_normalize_string_list(generated["exam_points"]),
    )
    return _to_response(row)


async def extract_target_knowledge(
    db: AsyncSession,
    *,
    current_user: User,
    target_id: int,
    force_regenerate: bool,
    material_id: int | None = None,
) -> KnowledgeExtractResponse:
    """Generate/save target-level extraction and refresh target knowledge graph.

    This synchronous path is kept for compatibility. New upload and frontend
    refresh flows use knowledge jobs so graph refreshes do not block requests.
    """
    response = await extract_target_summary(
        db,
        current_user=current_user,
        target_id=target_id,
        force_regenerate=force_regenerate,
    )
    graph = await KnowledgeGraphService.generate(
        db,
        current_user=current_user,
        payload=KnowledgeGraphGenerateRequest(
            target_id=target_id,
            material_id=material_id,
            force_regenerate=True,
            max_points=30 if material_id is not None else 12,
        ),
    )
    response.knowledge_graph = graph
    return response


async def extract_target_summary(
    db: AsyncSession,
    *,
    current_user: User,
    target_id: int,
    force_regenerate: bool,
) -> KnowledgeExtractResponse:
    """Generate/save target-level readable extraction without refreshing graph."""
    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=target_id,
        user_id=current_user.id,
    )
    if target is None:
        raise ValueError("课程/考试目标不存在")

    if not force_regenerate:
        existing = await KnowledgeRepository.get_latest(
            db,
            user_id=current_user.id,
            scope=ModelScope.target,
            target_id=target_id,
        )
        if existing is not None:
            return _to_response(existing)

    materials = await MaterialRepository.list_parsed_by_target(
        db,
        user_id=current_user.id,
        target_id=target_id,
    )
    if not materials:
        raise ValueError("该目标下暂无已解析资料，无法进行知识提炼")

    source_materials = _materials_for_knowledge(materials)
    if not source_materials:
        raise ValueError("该目标下已解析资料没有可用于知识提炼的文本")

    ai_usage_service.clear_pending_traces()
    try:
        generated = ai_service.generate_knowledge(
            "",
            target_name=target.title,
            subject=target.subject,
            scope="target",
            source_materials=source_materials,
        )
    finally:
        await ai_usage_service.record_pending_traces(
            db,
            user_id=current_user.id,
            target_id=target_id,
            material_id=None,
        )
    row = await KnowledgeRepository.save_extraction(
        db,
        user_id=current_user.id,
        scope=ModelScope.target,
        target_id=target_id,
        material_id=None,
        summary=str(generated["summary"]),
        outline=_normalize_string_list(generated["outline"]),
        keywords=_normalize_string_list(generated["keywords"]),
        key_points=_normalize_string_list(generated["key_points"]),
        exam_points=_normalize_string_list(generated["exam_points"]),
    )
    return _to_response(row)


async def extract_knowledge(
    db: AsyncSession,
    payload: KnowledgeExtractRequest,
    *,
    current_user: User,
) -> KnowledgeExtractResponse:
    """Run material-level or target-level extraction from one public endpoint."""
    if payload.material_id is not None:
        material = await MaterialRepository.get_by_id(
            db,
            material_id=payload.material_id,
            user_id=current_user.id,
        )
        if material is None:
            raise ValueError("资料不存在")
        if material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
            raise ValueError("资料未解析完成")
        if payload.target_id is not None and material.target_id != payload.target_id:
            raise ValueError("资料不属于该学习目标")
        if payload.target_id is None:
            return await extract_material_knowledge(
                db,
                current_user=current_user,
                material=material,
            )

    if payload.target_id is None:
        raise ValueError("material_id 或 target_id 至少需要提供一个")

    return await extract_target_knowledge(
        db,
        current_user=current_user,
        target_id=payload.target_id,
        force_regenerate=payload.force_regenerate,
        material_id=payload.material_id,
    )


async def get_latest_knowledge(
    db: AsyncSession,
    *,
    current_user: User,
    scope: KnowledgeExtractionScope,
    target_id: int | None = None,
    material_id: int | None = None,
) -> KnowledgeExtractResponse:
    """Return the newest stored extraction without starting a new AI call."""
    if scope == KnowledgeExtractionScope.material:
        if material_id is None:
            raise ValueError("资料级知识提炼需要提供 material_id")
        material = await MaterialRepository.get_by_id(
            db,
            material_id=material_id,
            user_id=current_user.id,
        )
        if material is None:
            raise ValueError("资料不存在")
        row = await KnowledgeRepository.get_latest(
            db,
            user_id=current_user.id,
            scope=ModelScope.material,
            material_id=material_id,
        )
    else:
        if target_id is None:
            raise ValueError("目标级知识提炼需要提供 target_id")
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")
        row = await KnowledgeRepository.get_latest(
            db,
            user_id=current_user.id,
            scope=ModelScope.target,
            target_id=target_id,
        )

    if row is None:
        raise LookupError("暂无知识提炼结果")

    graph = None
    if scope == KnowledgeExtractionScope.target and target_id is not None:
        graph = await KnowledgeGraphService.get_graph(
            db,
            current_user=current_user,
            target_id=target_id,
        )
    return _to_response(row, knowledge_graph=graph)


async def run_after_material_parsed(
    db: AsyncSession,
    *,
    current_user: User,
    material: Material,
) -> None:
    """Queue automatic knowledge jobs after one material is parsed successfully."""
    if material.parse_status != MaterialParseStatus.parsed or not material.parsed_text:
        return

    try:
        from app.services.knowledge_job_service import KnowledgeJobService

        await KnowledgeJobService.enqueue_after_material_parsed(
            db,
            current_user=current_user,
            material_id=material.id,
        )
    except Exception:
        await db.rollback()
        # Parsing has already succeeded. Knowledge extraction failures should
        # not turn a parsed material back into failed; manual /knowledge/extract
        # can be used to retry.
        return
