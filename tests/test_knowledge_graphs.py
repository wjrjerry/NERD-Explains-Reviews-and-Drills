"""Tests for target-level knowledge graph generation helpers."""

from app.schemas.knowledge_graph import KnowledgeGraphGenerateRequest, KnowledgePointNode
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
