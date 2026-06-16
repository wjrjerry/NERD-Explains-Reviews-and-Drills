"""Business service for AI question generation."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.material import Material
from app.models.knowledge_point import KnowledgePoint
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.schemas.question import (
    QuestionExplainResponse,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
    QuestionHintResponse,
    QuestionItem,
    QuestionOption,
    QuestionSolutionOption,
    QuestionSolutionResponse,
)
from app.services import ai_service, ai_usage_service


def _build_question_item_from_record(
    question: Question,
    *,
    point_ids: list[int] | None = None,
) -> QuestionItem:
    """Convert a persisted Question row into the public response schema."""
    return QuestionItem(
        id=question.id,
        type=question.question_type.value,
        stem=question.stem,
        options=[
            QuestionOption(
                key=str(option["key"]),
                text=str(option["text"]),
            )
            for option in question.options
        ],
        knowledge_points=[str(point) for point in question.knowledge_points],
        knowledge_point_ids=point_ids or [],
        difficulty=question.difficulty.value,
        hint_count=len(question.hints or []),
    )


def _join_material_text(materials: list[Material]) -> str:
    """Build a compact source text from parsed materials under one target."""
    chunks: list[str] = []
    for material in materials:
        parsed_text = (material.parsed_text or "").strip()
        if not parsed_text:
            continue
        chunks.append(
            f"资料ID {material.id}，文件名：{material.original_filename}\n{parsed_text}"
        )
    return "\n\n".join(chunks)


async def _select_auto_focus_points(
    db: AsyncSession,
    *,
    user_id: int,
    points: list[KnowledgePoint],
    count: int,
) -> list[KnowledgePoint]:
    """Pick target-level focus points from mastery weakness and importance.

    The first target-level version should avoid sending every graph node into
    the prompt. This ranking favors weak/low-accuracy points and then uses AI
    importance weight as the tie-breaker.
    """
    if not points:
        return []

    mastery_map = await KnowledgeGraphRepository.list_mastery_by_point_ids(
        db,
        user_id=user_id,
        point_ids=[point.id for point in points],
    )

    def rank(point: KnowledgePoint) -> tuple[float, float, int]:
        mastery = mastery_map.get(point.id)
        accuracy = mastery.accuracy if mastery is not None else 0.0
        answered_count = mastery.answered_count if mastery is not None else 0
        wrong_count = mastery.wrong_count if mastery is not None else 0
        weakness = 1.0 - accuracy
        if answered_count == 0:
            weakness += 0.25
        weakness += min(wrong_count, 5) * 0.05
        return (weakness, point.importance_weight, -point.sort_order)

    limit = min(len(points), max(count * 2, 3))
    return sorted(points, key=rank, reverse=True)[:limit]


async def _select_generation_scope(
    db: AsyncSession,
    payload: QuestionGenerateRequest,
    *,
    user_id: int,
    parsed_text: str | None,
) -> tuple[int, int | None, str, list[KnowledgePoint], str | None]:
    """Resolve material/target/knowledge-point context for question generation."""
    if payload.target_id is None:
        if payload.material_id is None or parsed_text is None:
            raise ValueError("按资料出题需要提供已解析资料文本")
        return payload.material_id, None, parsed_text, [], None

    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=payload.target_id,
        user_id=user_id,
    )
    if target is None:
        raise ValueError("课程/考试目标不存在")

    if payload.knowledge_point_ids:
        points = await KnowledgeGraphRepository.list_points_by_ids(
            db,
            user_id=user_id,
            target_id=payload.target_id,
            point_ids=payload.knowledge_point_ids,
        )
        found_ids = {point.id for point in points}
        missing_ids = [
            point_id for point_id in payload.knowledge_point_ids if point_id not in found_ids
        ]
        if missing_ids:
            raise ValueError(f"知识点不存在或不属于当前目标: {missing_ids}")
    else:
        points = await KnowledgeGraphRepository.list_points_by_target(
            db,
            user_id=user_id,
            target_id=payload.target_id,
        )
        points = await _select_auto_focus_points(
            db,
            user_id=user_id,
            points=points,
            count=payload.count,
        )

    if not points:
        raise ValueError("该目标下暂无知识点，请先生成知识图谱")

    materials = await MaterialRepository.list_parsed_by_target(
        db,
        user_id=user_id,
        target_id=payload.target_id,
    )
    if not materials:
        raise ValueError("该目标下暂无已解析资料，无法生成题目")

    primary_material_id = materials[0].id
    material_text = _join_material_text(materials)
    if not material_text:
        raise ValueError("该目标下已解析资料没有可用于出题的文本")

    return primary_material_id, payload.target_id, material_text, points, target.title


async def generate_questions(
    db: AsyncSession,
    payload: QuestionGenerateRequest,
    *,
    user_id: int,
    parsed_text: str | None = None,
) -> QuestionGenerateResponse:
    """Generate questions from material text and return structured items.

    Expected final workflow:
    1. Receive QuestionGenerateRequest from the router.
    2. Load parsed material text by payload.material_id.
    3. Call ai_service.generate_questions().
    4. Persist generated questions through question_repository.
    5. Return generated questions to the frontend.

    The router is responsible for authentication and material loading. This
    service owns AI generation and question persistence.
    """
    material_id, target_id, source_text, points, target_title = await _select_generation_scope(
        db,
        payload,
        user_id=user_id,
        parsed_text=parsed_text,
    )
    knowledge_point_ids = [point.id for point in points]
    ai_usage_service.clear_pending_traces()
    try:
        raw_questions = ai_service.generate_questions(
            source_text,
            material_id=material_id,
            question_types=[question_type.value for question_type in payload.question_types],
            difficulty=payload.difficulty.value,
            count=payload.count,
            target_title=target_title,
            extra_requirement=payload.extra_requirement,
            knowledge_points=[
                {
                    "id": point.id,
                    "name": point.name,
                    "description": point.description or "",
                    "importance_weight": point.importance_weight,
                }
                for point in points
            ],
        )
    finally:
        await ai_usage_service.record_pending_traces(
            db,
            user_id=user_id,
            target_id=target_id,
            material_id=material_id,
        )
    if points:
        point_id_by_name = {point.name: point.id for point in points}
        default_point_ids = [point.id for point in points]
        candidate_points = [
            {
                "id": point.id,
                "name": point.name,
                "description": point.description or "",
                "importance_weight": point.importance_weight,
            }
            for point in points
        ]
        for question in raw_questions:
            if not isinstance(question, dict):
                continue
            raw_names = question.get("knowledge_points", [])
            if not isinstance(raw_names, list):
                raw_names = []
            matched_ids = [
                point_id_by_name[str(name).strip()]
                for name in raw_names
                if str(name).strip() in point_id_by_name
            ]
            inferred_ids = ai_service.infer_question_knowledge_points(
                question,
                candidate_points,
            )
            question["knowledge_point_ids"] = (
                list(dict.fromkeys(matched_ids + inferred_ids)) or default_point_ids
            )

    saved_questions = await QuestionRepository.create_questions(
        db,
        user_id=user_id,
        material_id=material_id,
        target_id=target_id,
        knowledge_point_ids=knowledge_point_ids,
        questions=raw_questions,
    )
    link_map = await QuestionRepository.list_knowledge_point_ids_by_question_ids(
        db,
        question_ids=[question.id for question in saved_questions],
    )

    return QuestionGenerateResponse(
        material_id=material_id,
        target_id=target_id,
        questions=[
            _build_question_item_from_record(
                question,
                point_ids=link_map.get(question.id, []),
            )
            for question in saved_questions
        ],
    )


async def get_question_hint(
    db: AsyncSession,
    *,
    user_id: int,
    question_id: int,
    level: int,
) -> QuestionHintResponse:
    """Return one progressively stronger hint without exposing the answer."""
    question = await QuestionRepository.get_question_by_id(
        db,
        user_id=user_id,
        question_id=question_id,
    )
    if question is None:
        raise LookupError("Question not found.")

    hints = [str(hint).strip() for hint in (question.hints or []) if str(hint).strip()]
    if level < 1 or level > len(hints):
        raise LookupError("Hint not available.")

    return QuestionHintResponse(
        question_id=question.id,
        level=level,
        hint=hints[level - 1],
    )


async def get_question_solution(
    db: AsyncSession,
    *,
    user_id: int,
    question_id: int,
) -> QuestionSolutionResponse:
    """Return the stored answer and analysis for a question owned by the user."""
    question = await QuestionRepository.get_question_by_id(
        db,
        user_id=user_id,
        question_id=question_id,
    )
    if question is None:
        raise LookupError("Question not found.")

    return QuestionSolutionResponse(
        question_id=question.id,
        correct_answer=[str(answer) for answer in question.correct_answer],
        analysis=question.analysis,
        options=[
            QuestionSolutionOption(
                key=str(option.get("key", "")),
                text=str(option.get("text", "")),
                analysis=str(option.get("analysis", "")),
            )
            for option in question.options
        ],
    )


async def explain_question(
    db: AsyncSession,
    *,
    user_id: int,
    question_id: int,
    student_question: str,
) -> QuestionExplainResponse:
    """Answer a follow-up question about one generated question."""
    question = await QuestionRepository.get_question_by_id(
        db,
        user_id=user_id,
        question_id=question_id,
    )
    if question is None:
        raise LookupError("Question not found.")

    ai_usage_service.clear_pending_traces()
    try:
        answer = ai_service.explain_question(
            stem=question.stem,
            options=[
                {
                    "key": str(option.get("key", "")),
                    "text": str(option.get("text", "")),
                    "analysis": str(option.get("analysis", "")),
                }
                for option in question.options
            ],
            correct_answer=[str(answer) for answer in question.correct_answer],
            analysis=question.analysis,
            knowledge_points=[str(point) for point in question.knowledge_points],
            student_question=student_question,
        )
    finally:
        await ai_usage_service.record_pending_traces(
            db,
            user_id=user_id,
            target_id=question.target_id,
            material_id=question.material_id,
        )

    return QuestionExplainResponse(question_id=question.id, answer=answer)
