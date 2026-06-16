"""Tests for unified knowledge extraction request/response schemas."""

from app.schemas.knowledge import KnowledgeExtractRequest, KnowledgeExtractResponse
from app.services import ai_service


def test_knowledge_extract_request_accepts_material_scope():
    payload = KnowledgeExtractRequest(material_id=1)

    assert payload.material_id == 1
    assert payload.target_id is None


def test_knowledge_extract_request_accepts_target_scope():
    payload = KnowledgeExtractRequest(target_id=2, force_regenerate=True)

    assert payload.target_id == 2
    assert payload.force_regenerate is True


def test_knowledge_extract_request_accepts_target_material_incremental_scope():
    payload = KnowledgeExtractRequest(material_id=1, target_id=2)

    assert payload.material_id == 1
    assert payload.target_id == 2


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


def test_mock_knowledge_extraction_filters_file_metadata(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ai_provider", "mock")

    result = ai_service.generate_knowledge(
        "Chapter1.pdf Text Book Modern Compiler Implementation 词法分析 语法分析 中间代码生成",
        target_name="Chapter1.pdf",
    )

    normalized_keywords = {item.casefold() for item in result["keywords"]}
    assert "pdf" not in normalized_keywords
    assert "chapter1" not in normalized_keywords
    assert "词法分析" in result["keywords"]


def test_real_knowledge_extraction_uses_llm_and_cleans_keywords(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "ai_provider", "openai-compatible")
    captured: dict[str, object] = {}

    def fake_chat_completion(**kwargs):
        captured.update(kwargs)
        return """
        ```json
        {
          "summary": "资料围绕编译器前端展开，重点包括词法分析、语法分析和中间表示。",
          "outline": ["编译流程", "词法分析", "语法分析"],
          "keywords": ["pdf", "Chapter1", "Text", "词法分析", "语法分析", "中间表示"],
          "key_points": ["理解词法分析如何把字符流转换为 token。"],
          "exam_points": ["能够区分词法分析与语法分析的职责。"]
        }
        ```
        """

    monkeypatch.setattr(ai_service.llm_service, "chat_completion", fake_chat_completion)

    result = ai_service.generate_knowledge(
        "",
        target_name="编译原理",
        scope="target",
        subject="编译原理",
        source_materials=[
            {
                "material_id": 13,
                "title": "Chapter1.pdf",
                "content": "词法分析负责识别 token，语法分析负责构造语法树。",
            }
        ],
    )

    assert captured["task"] == "knowledge_extraction"
    assert "资料 JSON" in captured["user_prompt"]
    assert "词法分析" in result["keywords"]
    assert "语法分析" in result["keywords"]
    assert all(item.casefold() not in {"pdf", "chapter1", "text"} for item in result["keywords"])
