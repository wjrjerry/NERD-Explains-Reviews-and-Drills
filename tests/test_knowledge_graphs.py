"""Tests for target-level knowledge graph generation helpers."""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.knowledge_point import (
    KnowledgePoint,
    KnowledgePointSource,
    MasteryStatus,
    MaterialKnowledgePoint,
    UserKnowledgeMastery,
)
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.qa import QaKnowledgePoint, QaRecord
from app.models.question import (
    Question,
    QuestionDifficulty,
    QuestionKnowledgePoint,
    QuestionType,
)
from app.models.review_plan import ReviewPlan, ReviewPlanTask
from app.models.study_target import StudyTarget, StudyTargetType
from app.models.test_record import TestRecord
from app.models.user import User
from app.models.wrong_question import (
    MasteryStatus as WrongQuestionMasteryStatus,
)
from app.models.wrong_question import WrongQuestion, WrongQuestionKnowledgePoint
from app.repositories.knowledge_graph_repository import KnowledgePointCreateData
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.schemas.knowledge_graph import KnowledgeGraphGenerateRequest, KnowledgePointNode
from app.services.knowledge_graph_service import (
    _enrich_material_evidence,
    _normalize_graph_points,
    _validate_graph_merges,
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
    assert result["merges"] == []


def test_normalize_graph_merges_filters_invalid_items():
    merges = ai_service._normalize_graph_merges(
        [
            {"from_name": "需求分析", "to_name": "软件需求分析"},
            {"from_name": "需求分析", "to_name": "软件需求分析"},
            {"from_name": "", "to_name": "软件需求分析"},
            {"from_name": "测试", "to_name": "测试"},
            "invalid",
        ]
    )

    assert merges == [{"from_name": "需求分析", "to_name": "软件需求分析"}]


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


def test_validate_graph_merges_uses_existing_and_current_graphs():
    existing = [
        SimpleNamespace(name="需求分析"),
        SimpleNamespace(name="软件需求分析"),
        SimpleNamespace(name="概要设计"),
    ]
    current = [
        SimpleNamespace(name="软件需求分析"),
        SimpleNamespace(name="概要设计"),
    ]

    merges = _validate_graph_merges(
        [
            {"from_name": "需求分析", "to_name": "软件需求分析"},
            {"from_name": "不存在", "to_name": "软件需求分析"},
            {"from_name": "概要设计", "to_name": "需求分析"},
            {"from_name": "软件需求分析", "to_name": "概要设计"},
        ],
        existing_points=existing,
        current_points=current,
    )

    assert merges == [{"from_name": "需求分析", "to_name": "软件需求分析"}]


def test_validate_graph_merges_rejects_cycles():
    points = [
        SimpleNamespace(name="需求分析"),
        SimpleNamespace(name="软件需求分析"),
    ]

    merges = _validate_graph_merges(
        [
            {"from_name": "需求分析", "to_name": "软件需求分析"},
            {"from_name": "软件需求分析", "to_name": "需求分析"},
        ],
        existing_points=points,
        current_points=points,
    )

    assert merges == []


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


@pytest.mark.asyncio
async def test_merge_points_migrates_references_and_deletes_old_point(
    async_session_factory,
):
    async with async_session_factory() as db:
        suffix = datetime.now(timezone.utc).timestamp()
        user = User(username=f"merge-{suffix}", hashed_password="x")
        db.add(user)
        await db.flush()

        target = StudyTarget(
            user_id=user.id,
            title="软件工程复习",
            subject="软件工程",
            target_type=StudyTargetType.exam,
        )
        db.add(target)
        await db.flush()

        material = Material(
            user_id=user.id,
            target_id=target.id,
            original_filename="se.txt",
            stored_filename=f"se-{suffix}.txt",
            file_path="/tmp/se.txt",
            file_type=MaterialType.txt,
            file_size=100,
            parse_status=MaterialParseStatus.parsed,
            parsed_text="需求分析和软件需求分析。",
        )
        db.add(material)
        await db.flush()

        old_point = KnowledgePoint(
            user_id=user.id,
            target_id=target.id,
            name="需求分析",
            description="旧名称",
            importance_weight=0.8,
            level=1,
            sort_order=1,
            source=KnowledgePointSource.ai_generated,
        )
        new_point = KnowledgePoint(
            user_id=user.id,
            target_id=target.id,
            name="软件需求分析",
            description="新名称",
            importance_weight=0.9,
            level=1,
            sort_order=2,
            source=KnowledgePointSource.ai_generated,
        )
        db.add_all([old_point, new_point])
        await db.flush()

        child_point = KnowledgePoint(
            user_id=user.id,
            target_id=target.id,
            parent_id=old_point.id,
            name="用例建模",
            description="子节点",
            importance_weight=0.5,
            level=2,
            sort_order=1,
            source=KnowledgePointSource.ai_generated,
        )
        db.add(child_point)
        await db.flush()

        question = Question(
            user_id=user.id,
            material_id=material.id,
            target_id=target.id,
            question_type=QuestionType.single_choice,
            stem="需求分析的目标是什么？",
            options=[],
            correct_answer=["A"],
            analysis="明确需求。",
            hints=[],
            knowledge_points=["需求分析"],
            difficulty=QuestionDifficulty.medium,
        )
        qa = QaRecord(
            user_id=user.id,
            material_id=material.id,
            target_id=target.id,
            question="什么是需求分析？",
            answer="需求分析用于明确软件需求。",
            references=[],
            ai_provider="mock",
            ai_model=None,
        )
        record = TestRecord(
            user_id=user.id,
            material_id=material.id,
            target_id=target.id,
            score=0,
            accuracy=0,
            total_count=1,
            correct_count=0,
            wrong_count=1,
        )
        plan = ReviewPlan(
            user_id=user.id,
            target_id=target.id,
            title="复习计划",
            start_date=date(2026, 6, 16),
            end_date=date(2026, 6, 17),
            summary="",
        )
        db.add_all([question, qa, record, plan])
        await db.flush()

        wrong = WrongQuestion(
            user_id=user.id,
            test_record_id=record.id,
            question_id=question.id,
            target_id=target.id,
            material_id=material.id,
            stem=question.stem,
            user_answer=["B"],
            correct_answer=["A"],
            analysis="明确需求。",
            wrong_reason="混淆概念。",
            knowledge_points=["需求分析"],
            mastery_status=WrongQuestionMasteryStatus.unmastered,
        )
        task = ReviewPlanTask(
            plan_id=plan.id,
            task_date=date(2026, 6, 16),
            title="复习需求分析",
            content="复习错题",
            knowledge_point_id=old_point.id,
        )
        db.add_all([wrong, task])
        await db.flush()

        db.add_all(
            [
                QuestionKnowledgePoint(
                    question_id=question.id,
                    knowledge_point_id=old_point.id,
                    relevance_score=1.0,
                ),
                QuestionKnowledgePoint(
                    question_id=question.id,
                    knowledge_point_id=new_point.id,
                    relevance_score=1.0,
                ),
                WrongQuestionKnowledgePoint(
                    wrong_question_id=wrong.id,
                    knowledge_point_id=old_point.id,
                    wrong_reason="旧关联",
                    relevance_score=1.0,
                ),
                WrongQuestionKnowledgePoint(
                    wrong_question_id=wrong.id,
                    knowledge_point_id=new_point.id,
                    wrong_reason="新关联",
                    relevance_score=1.0,
                ),
                QaKnowledgePoint(
                    qa_record_id=qa.id,
                    knowledge_point_id=old_point.id,
                    relevance_score=1.0,
                ),
                MaterialKnowledgePoint(
                    material_id=material.id,
                    knowledge_point_id=old_point.id,
                    relevance_score=0.9,
                    evidence_text="旧证据",
                ),
                MaterialKnowledgePoint(
                    material_id=material.id,
                    knowledge_point_id=new_point.id,
                    relevance_score=0.3,
                    evidence_text="新证据",
                ),
                UserKnowledgeMastery(
                    user_id=user.id,
                    target_id=target.id,
                    knowledge_point_id=old_point.id,
                    mastery_status=MasteryStatus.weak,
                    mastery_score=0.5,
                    accuracy=0.5,
                    answered_count=2,
                    wrong_count=1,
                ),
                UserKnowledgeMastery(
                    user_id=user.id,
                    target_id=target.id,
                    knowledge_point_id=new_point.id,
                    mastery_status=MasteryStatus.proficient,
                    mastery_score=1.0,
                    accuracy=1.0,
                    answered_count=2,
                    wrong_count=0,
                ),
            ]
        )
        await db.commit()

        await KnowledgeGraphRepository.merge_points_for_target(
            db,
            user_id=user.id,
            target_id=target.id,
            merge_mappings=[
                {"from_name": "需求分析", "to_name": "软件需求分析"},
            ],
        )

        remaining_old = await db.get(KnowledgePoint, old_point.id)
        assert remaining_old is None

        await db.refresh(child_point)
        await db.refresh(task)
        assert child_point.parent_id == new_point.id
        assert task.knowledge_point_id == new_point.id

        question_links = (
            await db.execute(select(QuestionKnowledgePoint).where(
                QuestionKnowledgePoint.question_id == question.id
            ))
        ).scalars().all()
        wrong_links = (
            await db.execute(select(WrongQuestionKnowledgePoint).where(
                WrongQuestionKnowledgePoint.wrong_question_id == wrong.id
            ))
        ).scalars().all()
        qa_links = (
            await db.execute(select(QaKnowledgePoint).where(
                QaKnowledgePoint.qa_record_id == qa.id
            ))
        ).scalars().all()
        material_links = (
            await db.execute(select(MaterialKnowledgePoint).where(
                MaterialKnowledgePoint.knowledge_point_id == new_point.id
            ))
        ).scalars().all()
        mastery = (
            await db.execute(select(UserKnowledgeMastery).where(
                UserKnowledgeMastery.knowledge_point_id == new_point.id
            ))
        ).scalar_one()

        assert [link.knowledge_point_id for link in question_links] == [new_point.id]
        assert [link.knowledge_point_id for link in wrong_links] == [new_point.id]
        assert [link.knowledge_point_id for link in qa_links] == [new_point.id]
        assert len(material_links) == 1
        assert material_links[0].relevance_score == 0.9
        assert material_links[0].evidence_text == "旧证据"
        assert mastery.answered_count == 4
        assert mastery.wrong_count == 1
        assert mastery.accuracy == 0.75
        assert mastery.mastery_status == MasteryStatus.basic
