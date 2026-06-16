"""Business service for material-based AI question answering."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_point import KnowledgePoint
from app.models.material import Material
from app.models.qa import QaRecord
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.qa_repository import QaRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.knowledge_graph import KnowledgePointReference
from app.schemas.qa import QaAskRequest, QaAskResponse, QaHistoryItem, QaReference
from app.services import ai_service, ai_usage_service


def _normalize_references(
    references: list[dict[str, int | str]] | object,
) -> list[QaReference]:
    """Convert stored JSON references to response schema objects."""
    if not isinstance(references, list):
        return []

    normalized: list[QaReference] = []
    for reference in references:
        if not isinstance(reference, dict):
            continue

        try:
            normalized.append(
                QaReference(
                    material_id=int(reference["material_id"]),
                    snippet=str(reference["snippet"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return normalized


def _point_to_reference(point: KnowledgePoint) -> KnowledgePointReference:
    """Map a knowledge point ORM row to a compact response reference."""
    return KnowledgePointReference(
        id=point.id,
        name=point.name,
        importance_weight=point.importance_weight,
    )


def _to_history_item(
    record: QaRecord,
    *,
    knowledge_points: list[KnowledgePoint] | None = None,
) -> QaHistoryItem:
    """Map one QaRecord ORM object to the public history response."""
    return QaHistoryItem(
        qa_record_id=record.id,
        material_id=record.material_id,
        target_id=record.target_id,
        question=record.question,
        answer=record.answer,
        references=_normalize_references(record.references),
        knowledge_points=[
            _point_to_reference(point) for point in (knowledge_points or [])
        ],
        ai_provider=record.ai_provider,
        ai_model=record.ai_model,
        created_at=record.created_at.isoformat(),
    )


def _join_material_text(materials: list[Material]) -> str:
    """Build a target-level QA context from parsed materials."""
    chunks: list[str] = []
    for material in materials:
        parsed_text = (material.parsed_text or "").strip()
        if not parsed_text:
            continue
        chunks.append(
            f"资料ID {material.id}，文件名：{material.original_filename}\n{parsed_text}"
        )
    return "\n\n".join(chunks)


def _build_references_from_materials(materials: list[Material], question: str) -> list[QaReference]:
    """Select short material snippets for target-level QA references."""
    references: list[QaReference] = []
    question_terms = [term for term in question.replace("？", " ").replace("?", " ").split() if term]
    for material in materials:
        parsed_text = (material.parsed_text or "").strip()
        if not parsed_text:
            continue
        snippet = parsed_text[:160]
        for sentence in parsed_text.replace("？", "。").replace("!", "。").split("。"):
            sentence = sentence.strip()
            if sentence and any(term in sentence for term in question_terms):
                snippet = sentence[:160]
                break
        references.append(QaReference(material_id=material.id, snippet=snippet))
        if len(references) >= 3:
            break
    return references


def _requested_knowledge_point_ids(payload: QaAskRequest) -> list[int]:
    ids: list[int] = []
    if payload.knowledge_point_id is not None:
        ids.append(payload.knowledge_point_id)
    ids.extend(payload.knowledge_point_ids or [])

    unique_ids: list[int] = []
    seen: set[int] = set()
    for point_id in ids:
        try:
            normalized = int(point_id)
        except (TypeError, ValueError):
            continue
        if normalized <= 0 or normalized in seen:
            continue
        seen.add(normalized)
        unique_ids.append(normalized)
    return unique_ids


async def _resolve_qa_scope(
    db: AsyncSession,
    payload: QaAskRequest,
    *,
    user_id: int,
    parsed_text: str | None,
) -> tuple[int, int | None, str, list[QaReference], list[KnowledgePoint]]:
    """Resolve material/target/knowledge-point context for a QA request."""
    if payload.target_id is None:
        if payload.material_id is None or parsed_text is None:
            raise ValueError("按资料提问需要提供已解析资料文本")
        return payload.material_id, None, parsed_text, [], []

    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=payload.target_id,
        user_id=user_id,
    )
    if target is None:
        raise ValueError("课程/考试目标不存在")

    points: list[KnowledgePoint] = []
    requested_point_ids = _requested_knowledge_point_ids(payload)
    has_explicit_point = bool(requested_point_ids)
    if requested_point_ids:
        for point_id in requested_point_ids:
            point = await KnowledgeGraphRepository.get_point_by_id(
                db,
                user_id=user_id,
                point_id=point_id,
            )
            if point is None or point.target_id != payload.target_id:
                raise ValueError("知识点不存在或不属于当前目标")
            points.append(point)
    else:
        points = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=payload.target_id,
        )

    if payload.material_id is not None:
        material = await MaterialRepository.get_by_id(
            db,
            material_id=payload.material_id,
            user_id=user_id,
        )
        if material is None or material.target_id != payload.target_id:
            raise ValueError("资料不存在或不属于当前目标")
        if material.parse_status.value != "parsed" or not material.parsed_text:
            raise ValueError("资料尚未解析完成")
        return material.id, payload.target_id, material.parsed_text, [], points

    if has_explicit_point and points:
        evidence_rows = []
        for point in points:
            evidence_rows.extend(
                await KnowledgeGraphRepository.list_material_evidence_for_point(
                    db,
                    point_id=point.id,
                )
            )
        material_by_id: dict[int, Material] = {}
        for _link, material in evidence_rows:
            material_by_id.setdefault(material.id, material)
        material_ids = list(material_by_id)
        materials = list(material_by_id.values())
        if not materials:
            materials = await MaterialRepository.list_parsed_by_target(
                db,
                user_id=user_id,
                target_id=payload.target_id,
            )
            material_ids = [material.id for material in materials]
        references = [
            QaReference(
                material_id=material.id,
                snippet=link.evidence_text or (material.parsed_text or "")[:160],
            )
            for link, material in evidence_rows[:3]
        ]
    else:
        material_ids = []
        materials = await MaterialRepository.list_parsed_by_target(
            db,
            user_id=user_id,
            target_id=payload.target_id,
        )
        references = _build_references_from_materials(materials, payload.question)

    if not materials:
        raise ValueError("该目标下暂无已解析资料，无法回答")

    source_text = _join_material_text(materials)
    if not source_text:
        raise ValueError("该目标下已解析资料没有可用于回答的文本")

    primary_material_id = material_ids[0] if material_ids else materials[0].id
    return primary_material_id, payload.target_id, source_text, references, points


async def ask_question(
    db: AsyncSession,
    payload: QaAskRequest,
    *,
    user_id: int,
    parsed_text: str | None = None,
) -> QaAskResponse:
    """Coordinate material-based AI answering and QA response assembly.

    Expected final workflow:
    1. Receive QaAskRequest from the router.
    2. Load parsed material text by payload.material_id.
    3. Call ai_service.answer_question(parsed_text, question).
    4. Save question, answer, references, user_id, and material_id.
    5. Return the saved QA record for display.

    The router is still responsible for authentication and material loading.
    This service only coordinates AI generation and QA record persistence.
    """
    material_id, target_id, source_text, preset_references, points = await _resolve_qa_scope(
        db,
        payload,
        user_id=user_id,
        parsed_text=parsed_text,
    )
    ai_usage_service.clear_pending_traces()
    try:
        generated = ai_service.answer_question(
            source_text,
            payload.question,
            material_id=material_id,
        )
    finally:
        await ai_usage_service.record_pending_traces(
            db,
            user_id=user_id,
            target_id=target_id,
            material_id=material_id,
        )
    if target_id is not None and not _requested_knowledge_point_ids(payload) and points:
        candidate_points = [
            {
                "id": point.id,
                "name": point.name,
                "description": point.description or "",
                "importance_weight": point.importance_weight,
            }
            for point in points
        ]
        inferred_ids = set(
            ai_service.infer_qa_knowledge_points(
                question=payload.question,
                answer=str(generated["answer"]),
                candidate_points=candidate_points,
            )
        )
        points = [point for point in points if point.id in inferred_ids]
    references = preset_references or [
        QaReference(
            material_id=int(reference["material_id"]),
            snippet=str(reference["snippet"]),
        )
        for reference in generated["references"]
    ]

    record = await QaRepository.create_qa_record(
        db,
        user_id=user_id,
        material_id=material_id,
        target_id=target_id,
        knowledge_point_ids=[point.id for point in points],
        question=payload.question,
        answer=str(generated["answer"]),
        references=[reference.model_dump() for reference in references],
        ai_provider=settings.ai_provider,
        ai_model=settings.ai_model,
    )

    return QaAskResponse(
        qa_record_id=record.id,
        material_id=record.material_id,
        target_id=record.target_id,
        question=record.question,
        answer=record.answer,
        references=references,
        knowledge_points=[_point_to_reference(point) for point in points],
        created_at=record.created_at.isoformat(),
    )


async def list_history(
    db: AsyncSession,
    *,
    user_id: int,
    material_id: int | None,
    target_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[QaHistoryItem], int]:
    """List saved QA records owned by the current user."""
    records, total = await QaRepository.list_qa_records(
        db,
        user_id=user_id,
        material_id=material_id,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )
    point_map = await QaRepository.list_knowledge_points_by_qa_ids(
        db,
        qa_record_ids=[record.id for record in records],
    )
    return [
        _to_history_item(
            record,
            knowledge_points=point_map.get(record.id, []),
        )
        for record in records
    ], total
