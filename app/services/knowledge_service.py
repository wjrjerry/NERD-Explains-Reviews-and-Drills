"""Business service for the AI knowledge extraction module.

The service layer owns the business workflow. The router checks HTTP concerns,
while this file should eventually coordinate material data, AI generation, and
database persistence.
"""

from app.schemas.knowledge import KnowledgeExtractRequest, KnowledgeExtractResponse
from app.services import ai_service


def _build_mock_material_text(material_id: int) -> str:
    """Return temporary material text before member A's material module is ready.

    The final implementation should delete this helper and read parsed_text from
    the materials/document-content table. Keeping the mock here, instead of in
    the router, preserves the layer boundary: the router does HTTP work, while
    the service decides how to obtain business data.
    """
    return (
        f"资料 {material_id} 的示例解析文本。"
        "需求分析用于明确系统边界、用户角色、功能范围和验收标准。"
        "数据流图用于描述输入、处理过程、数据存储和输出之间的关系。"
        "AI知识提炼可以帮助学生从长篇资料中快速获得摘要、大纲、关键词、重点知识点和可能考点。"
    )


def _build_target_name(target_id: int | None) -> str | None:
    """Return temporary target name before target repository integration.

    Later this should query member A's study target module and use the real
    course/exam target name.
    """
    if target_id is None:
        return None
    return f"复习目标 {target_id}"


def extract_knowledge(
    payload: KnowledgeExtractRequest,
    *,
    parsed_text: str | None = None,
    target_name: str | None = None,
) -> KnowledgeExtractResponse:
    """Coordinate material loading, AI extraction, and result persistence.

    Expected final workflow:
    1. Receive KnowledgeExtractRequest from the router.
    2. Load parsed material text by payload.material_id.
    3. Call ai_service.generate_knowledge(parsed_text).
    4. Save the generated result through knowledge_repository.
    5. Return KnowledgeExtractResponse to the router.

    Current implementation:
    - Uses parsed_text if the caller passes it in.
    - Otherwise uses temporary mock material text so the flow can run before
      member A's material repository is finished.
    - Calls ai_service.generate_knowledge().
    - Does not save to the database yet.
    """
    # TODO: Add db session and user_id parameters when persistence is connected.
    # TODO: Load material by material_id through A module/repository.
    # TODO: Ensure material.parse_status is parsed if this check moves from router.
    # TODO: Read material.parsed_text as the AI input.
    # TODO: Call ai_service.generate_knowledge(parsed_text).
    # TODO: Save or update the extraction result through knowledge_repository.
    # TODO: Return KnowledgeExtractResponse.
    material_text = parsed_text or _build_mock_material_text(payload.material_id)
    resolved_target_name = target_name or _build_target_name(payload.target_id)
    generated = ai_service.generate_knowledge(
        material_text,
        target_name=resolved_target_name,
    )

    return KnowledgeExtractResponse(
        material_id=payload.material_id,
        summary=str(generated["summary"]),
        outline=list(generated["outline"]),
        keywords=list(generated["keywords"]),
        key_points=list(generated["key_points"]),
        exam_points=list(generated["exam_points"]),
    )
