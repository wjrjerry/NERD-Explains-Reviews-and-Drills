"""Tests for local knowledge-point inference helpers."""

from app.services import ai_service


def test_infer_question_knowledge_points_matches_stem_and_analysis():
    point_ids = ai_service.infer_question_knowledge_points(
        {
            "stem": "关于进程调度，下列说法正确的是？",
            "analysis": "时间片轮转是常见调度算法。",
            "knowledge_points": ["进程调度"],
        },
        [
            {
                "id": 1,
                "name": "进程调度",
                "description": "CPU 调度算法",
                "importance_weight": 0.8,
            },
            {
                "id": 2,
                "name": "文件系统",
                "description": "文件目录和索引节点",
                "importance_weight": 0.7,
            },
        ],
    )

    assert point_ids[0] == 1


def test_infer_qa_knowledge_points_matches_answer():
    point_ids = ai_service.infer_qa_knowledge_points(
        question="什么是死锁？",
        answer="死锁通常与互斥、占有并等待、不可剥夺、循环等待有关。",
        candidate_points=[
            {
                "id": 3,
                "name": "死锁",
                "description": "死锁条件、预防和避免",
                "importance_weight": 0.9,
            }
        ],
    )

    assert point_ids == [3]
