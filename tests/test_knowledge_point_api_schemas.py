"""Schema tests for knowledge point detail APIs."""

from app.schemas.knowledge_graph import (
    KnowledgePointMasteryUpdateRequest,
    KnowledgePointMaterialItem,
    KnowledgePointMaterialsResponse,
)


def test_knowledge_point_mastery_update_request_accepts_partial_update():
    payload = KnowledgePointMasteryUpdateRequest(
        mastery_status="basic",
        mastery_score=0.7,
    )

    assert payload.mastery_status == "basic"
    assert payload.mastery_score == 0.7
    assert payload.next_review_at is None


def test_knowledge_point_materials_response_shape():
    response = KnowledgePointMaterialsResponse(
        knowledge_point_id=1,
        items=[
            KnowledgePointMaterialItem(
                material_id=2,
                target_id=3,
                original_filename="os.txt",
                file_type="txt",
                parse_status="parsed",
                evidence_text="进程调度包括先来先服务和时间片轮转。",
                relevance_score=0.9,
            )
        ],
    )

    assert response.knowledge_point_id == 1
    assert response.items[0].material_id == 2
    assert response.items[0].evidence_text
