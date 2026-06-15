"""Tests for unified knowledge extraction request/response schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.knowledge import KnowledgeExtractRequest, KnowledgeExtractResponse


def test_knowledge_extract_request_accepts_material_scope():
    payload = KnowledgeExtractRequest(material_id=1)

    assert payload.material_id == 1
    assert payload.target_id is None


def test_knowledge_extract_request_accepts_target_scope():
    payload = KnowledgeExtractRequest(target_id=2, force_regenerate=True)

    assert payload.target_id == 2
    assert payload.force_regenerate is True


def test_knowledge_extract_request_rejects_ambiguous_scope():
    with pytest.raises(ValidationError):
        KnowledgeExtractRequest(material_id=1, target_id=2)


def test_knowledge_extract_response_allows_target_graph_field():
    response = KnowledgeExtractResponse(
        extraction_id=1,
        scope="target",
        material_id=None,
        target_id=2,
        summary="目标级摘要",
        outline=["大纲"],
        keywords=["关键词"],
        key_points=["重点"],
        exam_points=["考点"],
        knowledge_graph=None,
    )

    assert response.scope == "target"
    assert response.target_id == 2
