"""Business service for target-level knowledge graph generation and querying."""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import MasteryStatus
from app.models.knowledge_point import KnowledgePoint
from app.models.material import Material
from app.models.user import User
from app.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
    KnowledgePointCreateData,
)
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.knowledge_graph import (
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphResponse,
    KnowledgePointMaterialReference,
    KnowledgePointNode,
)
from app.services import ai_service, ai_usage_service

GRAPH_INPUT_MAX_CHARS = 12000


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
    existing_point_names: set[str] | None = None,
) -> list[KnowledgePointCreateData]:
    """Validate and normalize AI graph nodes before mutating the database."""
    normalized: list[KnowledgePointCreateData] = []
    seen_names: set[str] = set()
    existing_names = existing_point_names or set()

    for index, raw in enumerate(raw_points[:max_points]):
        name = str(raw.get("name", "")).strip()
        existing_name = str(raw.get("existing_name", "") or "").strip()
        if existing_name in existing_names:
            name = existing_name
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        parent_name = str(raw.get("parent_name", "") or "").strip() or None
        if (
            parent_name
            and parent_name not in seen_names
            and parent_name not in existing_names
        ):
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


def _extraction_text_for_ai(extraction) -> str:
    parts = [
        f"摘要：{extraction.summary}",
        "提纲：" + "；".join(str(item) for item in extraction.outline),
        "关键词：" + "；".join(str(item) for item in extraction.keywords),
        "复习重点：" + "；".join(str(item) for item in extraction.key_points),
        "可能考点：" + "；".join(str(item) for item in extraction.exam_points),
    ]
    return "\n".join(part for part in parts if part.strip("：； \n"))


def _string_items(value: object, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    return items[:limit] if limit is not None else items


def _fallback_graph_points_from_extractions(
    materials: list[Material],
    *,
    extraction_by_material_id: dict[int, object],
    max_points: int,
) -> list[dict[str, object]]:
    """Build a conservative graph from completed material extractions."""
    points: list[dict[str, object]] = []
    seen_names: set[str] = set()

    for material in materials:
        extraction = extraction_by_material_id.get(material.id)
        if extraction is None:
            continue
        candidate_names = [
            *_string_items(getattr(extraction, "keywords", []), limit=8),
            *_string_items(getattr(extraction, "outline", []), limit=4),
        ]
        descriptions = [
            *_string_items(getattr(extraction, "key_points", [])),
            *_string_items(getattr(extraction, "exam_points", [])),
        ]
        summary = str(getattr(extraction, "summary", "") or "").strip()

        for raw_name in candidate_names:
            name = raw_name.strip(" ，,。.；;：:")
            if len(name) < 2 or len(name) > 60:
                continue
            key = _normalize_point_name_for_merge(name)
            if not key or key in seen_names:
                continue
            seen_names.add(key)

            description = next(
                (item for item in descriptions if name.casefold() in item.casefold()),
                descriptions[len(points) % len(descriptions)] if descriptions else summary,
            )
            snippet = _matching_material_snippet(material.parsed_text or "", [name])
            if snippet is None:
                snippet = (description or summary or name)[:500]
            points.append(
                {
                    "name": name,
                    "existing_name": None,
                    "description": description[:240] if description else summary[:240],
                    "importance_weight": 0.72,
                    "parent_name": None,
                    "level": 2,
                    "sort_order": len(points) + 1,
                    "evidence": [
                        {
                            "material_id": material.id,
                            "snippet": snippet,
                            "relevance_score": 0.72,
                        }
                    ],
                }
            )
            if len(points) >= max_points:
                return points

    return points


def _materials_for_ai(
    materials: list[Material],
    *,
    extraction_by_material_id: dict[int, object] | None = None,
) -> list[dict[str, object]]:
    """Build compact material payloads for knowledge graph generation."""
    payload: list[dict[str, object]] = []
    extraction_by_material_id = extraction_by_material_id or {}
    remaining_chars = GRAPH_INPUT_MAX_CHARS
    for material in materials:
        if remaining_chars <= 0:
            break
        extraction = extraction_by_material_id.get(material.id)
        text = (
            _extraction_text_for_ai(extraction)
            if extraction is not None
            else material.parsed_text or ""
        )
        clipped = text[:remaining_chars]
        remaining_chars -= len(clipped)
        payload.append(
            {
                "material_id": material.id,
                "title": material.original_filename,
                "parsed_text": clipped,
            }
        )
    return payload


def _existing_points_for_ai(points) -> list[dict[str, object]]:
    """Build compact existing graph context so AI updates instead of replacing."""
    by_id = {point.id: point for point in points}
    payload: list[dict[str, object]] = []
    for point in points:
        parent = by_id.get(point.parent_id) if point.parent_id else None
        payload.append(
            {
                "name": point.name,
                "description": point.description,
                "importance_weight": point.importance_weight,
                "parent_name": parent.name if parent is not None else None,
                "level": point.level,
                "sort_order": point.sort_order,
            }
        )
    return payload


def _normalize_point_name_for_merge(name: str) -> str:
    """Use the repository's stable name key for merge validation."""
    return KnowledgeGraphRepository._normalize_point_name(name)


def _validate_graph_merges(
    raw_merges: object,
    *,
    existing_points: list[KnowledgePoint],
    current_points: list[KnowledgePoint],
) -> list[dict[str, str]]:
    """Validate AI-suggested merge mappings against target-local graph nodes."""
    if not isinstance(raw_merges, list):
        return []

    existing_names = {
        _normalize_point_name_for_merge(point.name): point.name
        for point in existing_points
    }
    current_names = {
        _normalize_point_name_for_merge(point.name): point.name
        for point in current_points
    }
    candidates: list[tuple[str, str]] = []

    for item in raw_merges:
        if not isinstance(item, dict):
            continue
        from_name = str(item.get("from_name", "") or "").strip()
        to_name = str(item.get("to_name", "") or "").strip()
        if not from_name or not to_name:
            continue
        from_key = _normalize_point_name_for_merge(from_name)
        to_key = _normalize_point_name_for_merge(to_name)
        if (
            not from_key
            or not to_key
            or from_key == to_key
            or from_key not in existing_names
            or to_key not in current_names
        ):
            continue
        candidates.append((from_key, to_key))

    validated: list[dict[str, str]] = []
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    candidate_graph = {from_key: to_key for from_key, to_key in candidates}

    def has_path(start_key: str, target_key: str) -> bool:
        visited: set[str] = set()
        current = start_key
        while current in candidate_graph and current not in visited:
            if current == target_key:
                return True
            visited.add(current)
            current = candidate_graph[current]
        return current == target_key

    for from_key, to_key in candidates:
        if (
            from_key in seen_sources
            or from_key in seen_targets
            or (from_key, to_key) in seen_pairs
            or has_path(to_key, from_key)
        ):
            continue
        seen_sources.add(from_key)
        seen_targets.add(to_key)
        seen_pairs.add((from_key, to_key))
        validated.append(
            {
                "from_name": existing_names[from_key],
                "to_name": current_names[to_key],
            }
        )
    return validated


def _point_match_terms(point: KnowledgePointCreateData) -> list[str]:
    """Extract conservative terms for linking a point to all parsed materials."""
    candidates = [point.name]
    candidates.extend(
        part.strip()
        for part in re.split(r"[\s,，。:：;；/\\()（）\[\]【】]+", point.name)
    )
    if point.description:
        candidates.extend(
            part.strip()
            for part in re.split(r"[\s,，。:：;；/\\()（）\[\]【】]+", point.description)
        )

    terms: list[str] = []
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        if candidate not in terms:
            terms.append(candidate)
    return sorted(terms, key=len, reverse=True)[:12]


def _matching_material_snippet(text: str, terms: list[str]) -> str | None:
    """Return a compact source snippet when a point term occurs in a material."""
    compact = text.strip()
    lowered = compact.casefold()
    for term in terms:
        index = lowered.find(term.casefold())
        if index < 0:
            continue
        start = max(0, index - 120)
        end = min(len(compact), index + len(term) + 220)
        return compact[start:end].strip()[:500]
    return None


def _enrich_material_evidence(
    points: list[KnowledgePointCreateData],
    materials: list[Material],
) -> list[KnowledgePointCreateData]:
    """Link generated points against every parsed material, not only new files."""
    enriched: list[KnowledgePointCreateData] = []
    for point in points:
        evidence_by_material: dict[int, dict[str, object]] = {}
        for evidence in point.evidence:
            try:
                material_id = int(evidence.get("material_id"))
            except (TypeError, ValueError):
                continue
            evidence_by_material[material_id] = evidence

        terms = _point_match_terms(point)
        for material in materials:
            if material.id in evidence_by_material:
                continue
            snippet = _matching_material_snippet(material.parsed_text or "", terms)
            if snippet is None:
                continue
            evidence_by_material[material.id] = {
                "material_id": material.id,
                "snippet": snippet,
                "relevance_score": 0.75,
            }

        enriched.append(
            KnowledgePointCreateData(
                name=point.name,
                description=point.description,
                importance_weight=point.importance_weight,
                parent_name=point.parent_name,
                level=point.level,
                sort_order=point.sort_order,
                evidence=list(evidence_by_material.values()),
            )
        )
    return enriched


def _append_existing_points_for_material_links(
    points: list[KnowledgePointCreateData],
    *,
    existing_points: list[KnowledgePoint],
    material: Material,
) -> list[KnowledgePointCreateData]:
    """Add existing points that match the current material so sync creates links."""
    existing_by_id = {point.id: point for point in existing_points}
    included_names = {
        KnowledgeGraphRepository._normalize_point_name(point.name) for point in points
    }
    appended = list(points)

    for point in existing_points:
        key = KnowledgeGraphRepository._normalize_point_name(point.name)
        if key in included_names:
            continue

        candidate = KnowledgePointCreateData(
            name=point.name,
            description=point.description,
            importance_weight=point.importance_weight,
            parent_name=existing_by_id.get(point.parent_id).name if point.parent_id in existing_by_id else None,
            level=point.level,
            sort_order=point.sort_order,
            evidence=[],
        )
        snippet = _matching_material_snippet(
            material.parsed_text or "",
            _point_match_terms(candidate),
        )
        if snippet is None:
            continue
        appended.append(
            KnowledgePointCreateData(
                name=candidate.name,
                description=candidate.description,
                importance_weight=candidate.importance_weight,
                parent_name=candidate.parent_name,
                level=candidate.level,
                sort_order=candidate.sort_order,
                evidence=[
                    {
                        "material_id": material.id,
                        "snippet": snippet,
                        "relevance_score": 0.75,
                    }
                ],
            )
        )
        included_names.add(key)

    return appended


async def _lock_target_graph_generation(db: AsyncSession, *, target_id: int) -> bool:
    """Serialize graph updates per target to avoid duplicate nodes from races."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    await db.execute(
        text("SELECT pg_advisory_lock(:lock_key)"),
        {"lock_key": 41_000_000 + target_id},
    )
    return True


async def _unlock_target_graph_generation(db: AsyncSession, *, target_id: int) -> None:
    """Release a session-level target graph lock."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await db.execute(
        text("SELECT pg_advisory_unlock(:lock_key)"),
        {"lock_key": 41_000_000 + target_id},
    )


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

        locked = await _lock_target_graph_generation(db, target_id=payload.target_id)
        try:
            existing = await KnowledgeGraphRepository.list_points_by_target(
                db,
                user_id=current_user.id,
                target_id=payload.target_id,
            )
            if existing and not payload.force_regenerate and payload.material_id is None:
                return await KnowledgeGraphService.get_graph(
                    db,
                    current_user=current_user,
                    target_id=payload.target_id,
                )

            focus_material: Material | None = None
            if payload.material_id is not None:
                focus_material = await MaterialRepository.get_by_id(
                    db,
                    material_id=payload.material_id,
                    user_id=current_user.id,
                )
                if focus_material is None or focus_material.target_id != payload.target_id:
                    raise ValueError("资料不存在或不属于当前目标")
                if focus_material.parse_status.value != "parsed" or not (focus_material.parsed_text or "").strip():
                    raise ValueError("资料尚未解析完成或没有可用于图谱的文本")
                materials = [focus_material]
            else:
                materials = await MaterialRepository.list_parsed_by_target(
                    db,
                    user_id=current_user.id,
                    target_id=payload.target_id,
                )
            if not materials:
                raise ValueError("该目标下暂无已解析资料，无法生成知识图谱")

            material_extractions = await KnowledgeRepository.list_latest_material_extractions_by_target(
                db,
                user_id=current_user.id,
                target_id=payload.target_id,
            )
            extraction_by_material_id = {
                extraction.material_id: extraction
                for extraction in material_extractions
                if extraction.material_id is not None
            }
            ai_usage_service.clear_pending_traces()
            try:
                ai_result = ai_service.generate_knowledge_graph(
                    target_title=target.title,
                    subject=target.subject,
                    materials=_materials_for_ai(
                        materials,
                        extraction_by_material_id=extraction_by_material_id,
                    ),
                    existing_points=_existing_points_for_ai(existing),
                    max_points=payload.max_points,
                )
            except Exception:
                fallback_points = _fallback_graph_points_from_extractions(
                    materials,
                    extraction_by_material_id=extraction_by_material_id,
                    max_points=payload.max_points,
                )
                if not fallback_points:
                    raise
                ai_result = {"points": fallback_points, "merges": []}
            finally:
                await ai_usage_service.record_pending_traces(
                    db,
                    user_id=current_user.id,
                    target_id=payload.target_id,
                    material_id=payload.material_id,
                )
            raw_points = ai_result.get("points", [])
            if not isinstance(raw_points, list):
                raise ValueError("AI 知识图谱返回格式错误")

            normalized_points = _normalize_graph_points(
                raw_points,
                valid_material_ids={material.id for material in materials},
                max_points=payload.max_points,
                existing_point_names={point.name for point in existing},
            )
            normalized_points = _enrich_material_evidence(normalized_points, materials)
            if focus_material is not None and existing:
                normalized_points = _append_existing_points_for_material_links(
                    normalized_points,
                    existing_points=existing,
                    material=focus_material,
                )
            synced_points = await KnowledgeGraphRepository.sync_graph_for_target(
                db,
                user_id=current_user.id,
                target_id=payload.target_id,
                points=normalized_points,
            )
            merge_mappings = _validate_graph_merges(
                ai_result.get("merges", []),
                existing_points=existing,
                current_points=synced_points,
            )
            if merge_mappings:
                await KnowledgeGraphRepository.merge_points_for_target(
                    db,
                    user_id=current_user.id,
                    target_id=payload.target_id,
                    merge_mappings=merge_mappings,
                )
            return await KnowledgeGraphService.get_graph(
                db,
                current_user=current_user,
                target_id=payload.target_id,
            )
        finally:
            if locked:
                await _unlock_target_graph_generation(db, target_id=payload.target_id)

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
