"""Tests for target-level knowledge graph generation helpers."""

from types import SimpleNamespace

from app.repositories.knowledge_graph_repository import KnowledgePointCreateData
from app.schemas.knowledge_graph import KnowledgeGraphGenerateRequest, KnowledgePointNode
from app.services.knowledge_graph_service import (
    _enrich_material_evidence,
    _normalize_graph_points,
)
from app.services import ai_service


def test_mock_generate_knowledge_graph_returns_weighted_points(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ai_provider", "mock")

    result = ai_service.generate_knowledge_graph(
        target_title="软件工程复习",
        subject="软件工程",
        materials=[
            {
                "material_id": 1,
                "title": "需求分析.txt",
                "parsed_text": "需求分析用于明确系统边界、用户角色、功能范围和验收标准。系统设计关注架构、模块划分和接口设计。",
            }
        ],
        max_points=5,
    )

    assert "points" in result
    assert result["points"]

    first = result["points"][0]
    assert first["name"]
    assert 0 <= first["importance_weight"] <= 1
    assert first["level"] == 1
    assert first["evidence"][0]["material_id"] == 1
    assert first["evidence"][0]["snippet"]


def test_knowledge_graph_generate_request_limits_point_count():
    payload = KnowledgeGraphGenerateRequest(target_id=1, max_points=3)

    assert payload.target_id == 1
    assert payload.force_regenerate is False
    assert payload.max_points == 3


def test_enrich_material_evidence_links_new_point_to_existing_materials():
    points = [
        KnowledgePointCreateData(
            name="需求分析",
            description="明确系统边界和验收标准",
            importance_weight=0.9,
            parent_name=None,
            level=1,
            sort_order=1,
            evidence=[
                {
                    "material_id": 2,
                    "snippet": "新资料也提到了需求分析。",
                    "relevance_score": 1.0,
                }
            ],
        )
    ]
    materials = [
        SimpleNamespace(id=1, parsed_text="旧资料：需求分析用于明确系统边界。"),
        SimpleNamespace(id=2, parsed_text="新资料也提到了需求分析。"),
    ]

    enriched = _enrich_material_evidence(points, materials)

    evidence_material_ids = {
        int(item["material_id"]) for item in enriched[0].evidence
    }
    assert evidence_material_ids == {1, 2}


def test_normalize_graph_points_allows_parent_from_existing_graph():
    points = _normalize_graph_points(
        [
            {
                "name": "用例建模",
                "description": "根据需求分析扩展出的子知识点",
                "importance_weight": 0.7,
                "parent_name": "需求分析",
                "level": 2,
                "sort_order": 1,
                "evidence": [{"material_id": 1, "snippet": "用例建模", "relevance_score": 0.8}],
            }
        ],
        valid_material_ids={1},
        max_points=5,
        existing_point_names={"需求分析"},
    )

    assert points[0].parent_name == "需求分析"


def test_normalize_graph_points_uses_existing_name_to_reuse_node():
    points = _normalize_graph_points(
        [
            {
                "name": "风险",
                "existing_name": "风险识别",
                "description": "项目管理中的风险相关内容",
                "importance_weight": 0.7,
                "parent_name": "项目管理",
                "level": 2,
                "sort_order": 1,
                "evidence": [{"material_id": 1, "snippet": "风险", "relevance_score": 0.8}],
            }
        ],
        valid_material_ids={1},
        max_points=5,
        existing_point_names={"项目管理", "风险识别"},
    )

    assert points[0].name == "风险识别"


def test_knowledge_point_node_schema_contains_mastery_fields():
    node = KnowledgePointNode(
        id=1,
        parent_id=None,
        name="需求分析",
        description="明确系统边界、角色和验收标准",
        importance_weight=0.9,
        level=1,
        sort_order=1,
        mastery_status="unlearned",
        mastery_score=0.0,
        accuracy=0.0,
        answered_count=0,
        wrong_count=0,
        materials=[],
    )

    assert node.name == "需求分析"
    assert node.mastery_status == "unlearned"
    assert node.materials == []
