"""Business service for target-level knowledge graph generation and querying."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import MasteryStatus
from app.models.material import Material
from app.models.user import User
from app.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
    KnowledgePointCreateData,
)
from app.repositories.material_repository import MaterialRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.knowledge_graph import (
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphResponse,
    KnowledgePointMaterialReference,
    KnowledgePointNode,
)
from app.services import ai_service, ai_usage_service


def _clamp_weight(value: object) -> float:
    """Normalize AI-returned importance weight into [0, 1]."""
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(max(weight, 0.0), 1.0)


def _safe_int(value: object, default: int) -> int:
    """Normalize AI-returned integer-like values."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_graph_points(
    raw_points: list[dict[str, object]],
    *,
    valid_material_ids: set[int],
    max_points: int,
) -> list[KnowledgePointCreateData]:
    """Validate and normalize AI graph nodes before mutating the database."""
    normalized: list[KnowledgePointCreateData] = []
    seen_names: set[str] = set()

    for index, raw in enumerate(raw_points[:max_points]):
        name = str(raw.get("name", "")).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        parent_name = str(raw.get("parent_name", "") or "").strip() or None
        if parent_name and parent_name not in seen_names:
            parent_name = None

        evidence_items: list[dict[str, object]] = []
        raw_evidence = raw.get("evidence", [])
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                if not isinstance(item, dict):
                    continue
                try:
                    material_id = int(item.get("material_id"))
                except (TypeError, ValueError):
                    continue
                if material_id not in valid_material_ids:
                    continue
                snippet = str(item.get("snippet", "") or "").strip()
                evidence_items.append(
                    {
                        "material_id": material_id,
                        "snippet": snippet[:500],
                        "relevance_score": _clamp_weight(item.get("relevance_score", 1.0)),
                    }
                )

        normalized.append(
            KnowledgePointCreateData(
                name=name,
                description=str(raw.get("description", "") or "").strip() or None,
                importance_weight=_clamp_weight(raw.get("importance_weight", 0.5)),
                parent_name=parent_name,
                level=max(1, _safe_int(raw.get("level", 1), 1)),
                sort_order=_safe_int(raw.get("sort_order", index + 1), index + 1),
                evidence=evidence_items,
            )
        )

    if not normalized:
        raise ValueError("AI 未生成有效知识点")

    return normalized


def _materials_for_ai(materials: list[Material]) -> list[dict[str, object]]:
    """Build compact material payloads for knowledge graph generation."""
    return [
        {
            "material_id": material.id,
            "title": material.original_filename,
            "parsed_text": material.parsed_text or "",
        }
        for material in materials
    ]


class KnowledgeGraphService:
    """Service for generating and querying target-level knowledge graphs."""

    @staticmethod
    async def generate(
        db: AsyncSession,
        *,
        current_user: User,
        payload: KnowledgeGraphGenerateRequest,
    ) -> KnowledgeGraphResponse:
        """Generate or reuse a knowledge graph for one study target."""
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=payload.target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")

        existing = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=current_user.id,
            target_id=payload.target_id,
        )
        if existing and not payload.force_regenerate:
            return await KnowledgeGraphService.get_graph(
                db,
                current_user=current_user,
                target_id=payload.target_id,
            )

        materials = await MaterialRepository.list_parsed_by_target(
            db,
            user_id=current_user.id,
            target_id=payload.target_id,
        )
        if not materials:
            raise ValueError("该目标下暂无已解析资料，无法生成知识图谱")

        ai_usage_service.clear_pending_traces()
        try:
            ai_result = ai_service.generate_knowledge_graph(
                target_title=target.title,
                subject=target.subject,
                materials=_materials_for_ai(materials),
                max_points=payload.max_points,
            )
        finally:
            await ai_usage_service.record_pending_traces(
                db,
                user_id=current_user.id,
                target_id=payload.target_id,
                material_id=None,
            )
        raw_points = ai_result.get("points", [])
        if not isinstance(raw_points, list):
            raise ValueError("AI 知识图谱返回格式错误")

        normalized_points = _normalize_graph_points(
            raw_points,
            valid_material_ids={material.id for material in materials},
            max_points=payload.max_points,
        )
        await KnowledgeGraphRepository.replace_graph_for_target(
            db,
            user_id=current_user.id,
            target_id=payload.target_id,
            points=normalized_points,
        )
        return await KnowledgeGraphService.get_graph(
            db,
            current_user=current_user,
            target_id=payload.target_id,
        )

    @staticmethod
    async def get_graph(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
    ) -> KnowledgeGraphResponse:
        """Return graph nodes with mastery and material evidence."""
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=current_user.id,
        )
        if target is None:
            raise ValueError("课程/考试目标不存在")

        points = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=current_user.id,
            target_id=target_id,
        )
        point_ids = [point.id for point in points]
        mastery_map = await KnowledgeGraphRepository.list_mastery_by_point_ids(
            db,
            user_id=current_user.id,
            point_ids=point_ids,
        )
        material_links = await KnowledgeGraphRepository.list_material_links_by_point_ids(
            db,
            point_ids=point_ids,
        )

        nodes: list[KnowledgePointNode] = []
        for point in points:
            mastery = mastery_map.get(point.id)
            links = material_links.get(point.id, [])
            nodes.append(
                KnowledgePointNode(
                    id=point.id,
                    parent_id=point.parent_id,
                    name=point.name,
                    description=point.description,
                    importance_weight=point.importance_weight,
                    level=point.level,
                    sort_order=point.sort_order,
                    mastery_status=mastery.mastery_status if mastery else MasteryStatus.unlearned,
                    mastery_score=mastery.mastery_score if mastery else 0.0,
                    accuracy=mastery.accuracy if mastery else 0.0,
                    answered_count=mastery.answered_count if mastery else 0,
                    wrong_count=mastery.wrong_count if mastery else 0,
                    materials=[
                        KnowledgePointMaterialReference(
                            material_id=link.material_id,
                            evidence_text=link.evidence_text,
                            relevance_score=link.relevance_score,
                        )
                        for link in links
                    ],
                )
            )

        return KnowledgeGraphResponse(
            target_id=target_id,
            nodes=nodes,
            generated_at=max((point.created_at for point in points), default=None),
        )
