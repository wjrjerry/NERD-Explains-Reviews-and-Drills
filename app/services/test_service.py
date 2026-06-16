"""Business service for self-test submission and automatic scoring."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.repositories.question_repository import QuestionRepository
from app.repositories.test_record_repository import TestRecordRepository
from app.schemas.test_record import (
    KnowledgePointTestSummary,
    TestAnswerItem,
    TestResultItem,
    TestSubmitRequest,
    TestSubmitResponse,
)
from app.services import (
    ai_service,
    ai_usage_service,
    knowledge_mastery_service,
    wrong_question_service,
)
from app.services.knowledge_mastery_service import KnowledgeMasteryAnswerOutcome


OBJECTIVE_QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false"}


def _normalize_answer(answer: list[str]) -> list[str]:
    """Normalize objective answers for order-insensitive comparison."""
    return sorted({str(item).strip() for item in answer if str(item).strip()})


def _question_map(questions: list[Question]) -> dict[int, Question]:
    """Build a lookup map for submitted question IDs."""
    return {question.id: question for question in questions}


def _build_wrong_reason(question: Question, user_answer: list[str]) -> str:
    """Build a simple wrong-answer reason before AI analysis is connected."""
    if question.question_type.value == "subjective":
        submitted = user_answer[0] if user_answer else "未作答"
        return f"本题主观作答为：{submitted}。请结合参考答案和评分反馈补充关键要点。"

    selected = "、".join(user_answer) if user_answer else "未作答"
    correct = "、".join(_normalize_answer(question.correct_answer))
    return f"本题选择为 {selected}，正确答案为 {correct}。请结合解析复习相关知识点。"


def _extract_submitted_answer(item: TestAnswerItem, question: Question) -> list[str]:
    """Normalize submitted answer while reserving file/PDF inputs for OCR."""
    question_type = question.question_type.value
    if question_type in OBJECTIVE_QUESTION_TYPES:
        if item.answer_text:
            raise ValueError("objective questions must use answer, not answer_text")
        if item.answer_file_ids or item.answer_file_urls:
            raise ValueError("OCR answer parsing is not connected yet")
        return _normalize_answer(item.answer)

    text_answer = (item.answer_text or "").strip()
    if not text_answer and item.answer:
        text_answer = "\n".join(str(answer).strip() for answer in item.answer if str(answer).strip())
    if not text_answer and (item.answer_file_ids or item.answer_file_urls):
        raise ValueError("OCR answer parsing is not connected yet")
    return [text_answer] if text_answer else []


def _score_objective_answer(
    question: Question,
    user_answer: list[str],
) -> tuple[float, bool, str, str, list[str], list[str], list[str]]:
    """Score objective answer locally."""
    correct_answer = _normalize_answer(question.correct_answer)
    is_correct = user_answer == correct_answer
    score = 1.0 if is_correct else 0.0
    if is_correct:
        return score, is_correct, question.analysis, "", [], [], []

    selected_set = set(user_answer)
    option_feedback = [
        str(option.get("analysis", "")).strip()
        for option in question.options
        if str(option.get("key", "")).strip() in selected_set
        and str(option.get("analysis", "")).strip()
    ]
    missing_points = option_feedback or [question.analysis]
    wrong_reason = _build_wrong_reason(question, user_answer)
    return score, is_correct, question.analysis, wrong_reason, [], missing_points, []


def _score_subjective_answer(
    question: Question,
    user_answer: list[str],
) -> tuple[float, bool, str, str, list[str], list[str], list[str]]:
    """Score subjective answer through AI."""
    scoring = ai_service.score_subjective_answer(
        stem=question.stem,
        reference_answer=[str(answer) for answer in question.correct_answer],
        analysis=question.analysis,
        knowledge_points=[str(point) for point in question.knowledge_points],
        user_answer=user_answer[0] if user_answer else "",
    )
    score = float(scoring["score"])
    is_correct = bool(scoring["is_correct"])
    analysis = str(scoring["analysis"])
    wrong_reason = str(scoring["wrong_reason"])
    matched_points = [str(point) for point in scoring["matched_points"]]
    missing_points = [str(point) for point in scoring["missing_points"]]
    misconceptions = [str(point) for point in scoring["misconceptions"]]
    return (
        score,
        is_correct,
        analysis,
        wrong_reason,
        matched_points,
        missing_points,
        misconceptions,
    )


def _build_knowledge_point_summary(
    results: list[TestResultItem],
) -> list[KnowledgePointTestSummary]:
    """Aggregate this submission's result by linked knowledge point."""
    stats: dict[int, dict[str, float | int]] = {}
    for result in results:
        for point_id in result.knowledge_point_ids:
            item = stats.setdefault(
                point_id,
                {
                    "total_count": 0,
                    "correct_count": 0,
                    "score_sum": 0.0,
                },
            )
            item["total_count"] = int(item["total_count"]) + 1
            item["correct_count"] = int(item["correct_count"]) + (1 if result.is_correct else 0)
            item["score_sum"] = float(item["score_sum"]) + float(result.score)

    summaries: list[KnowledgePointTestSummary] = []
    for point_id, item in sorted(stats.items()):
        total_count = int(item["total_count"])
        correct_count = int(item["correct_count"])
        wrong_count = total_count - correct_count
        summaries.append(
            KnowledgePointTestSummary(
                knowledge_point_id=point_id,
                total_count=total_count,
                correct_count=correct_count,
                wrong_count=wrong_count,
                accuracy=round(correct_count / total_count, 4) if total_count else 0.0,
                average_score=round(float(item["score_sum"]) / total_count, 4)
                if total_count
                else 0.0,
            )
        )
    return summaries


async def score_single_answer(
    db: AsyncSession,
    *,
    user_id: int,
    question: Question,
    submitted: TestAnswerItem,
    target_id: int | None,
    material_id: int,
    knowledge_point_ids: list[int],
) -> tuple[TestResultItem, str]:
    """Score one submitted answer and return the public result plus wrong reason."""
    user_answer = _extract_submitted_answer(submitted, question)
    if question.question_type.value in OBJECTIVE_QUESTION_TYPES:
        correct_answer = _normalize_answer(question.correct_answer)
        ai_usage_service.clear_pending_traces()
        try:
            (
                item_score,
                is_correct,
                item_analysis,
                wrong_reason,
                matched_points,
                missing_points,
                misconceptions,
            ) = _score_objective_answer(question, user_answer)
        finally:
            await ai_usage_service.record_pending_traces(
                db,
                user_id=user_id,
                target_id=target_id or question.target_id,
                material_id=material_id,
            )
    else:
        correct_answer = [
            str(answer).strip()
            for answer in question.correct_answer
            if str(answer).strip()
        ]
        ai_usage_service.clear_pending_traces()
        try:
            (
                item_score,
                is_correct,
                item_analysis,
                wrong_reason,
                matched_points,
                missing_points,
                misconceptions,
            ) = _score_subjective_answer(question, user_answer)
        finally:
            await ai_usage_service.record_pending_traces(
                db,
                user_id=user_id,
                target_id=target_id or question.target_id,
                material_id=material_id,
            )

    result = TestResultItem(
        question_id=question.id,
        knowledge_point_ids=knowledge_point_ids,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        score=item_score,
        analysis=item_analysis,
        matched_points=matched_points,
        missing_points=missing_points,
        misconceptions=misconceptions,
    )
    return result, wrong_reason or _build_wrong_reason(question, user_answer)


async def submit_test(
    db: AsyncSession,
    payload: TestSubmitRequest,
    *,
    user_id: int,
) -> TestSubmitResponse:
    """Score submitted answers and create a test record.

    Current scope:
    - Load persisted questions by ID.
    - Ensure all questions belong to current user and requested material.
    - Compare answers and save test_records/test_answer_records.

    Next step:
    - Use wrong answers from the saved answer records to create wrong_questions.
    """
    if not payload.answers:
        raise ValueError("answers cannot be empty")

    question_ids = [item.question_id for item in payload.answers]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("duplicate question_id is not allowed")

    questions = await QuestionRepository.list_by_ids(
        db,
        user_id=user_id,
        question_ids=question_ids,
    )
    questions_by_id = _question_map(questions)
    missing_ids = [
        question_id for question_id in question_ids if question_id not in questions_by_id
    ]
    if missing_ids:
        raise LookupError(f"questions not found: {missing_ids}")

    invalid_material_ids = [
        question.id
        for question in questions
        if question.material_id != payload.material_id
    ]
    if invalid_material_ids:
        raise ValueError(
            f"questions do not belong to material {payload.material_id}: {invalid_material_ids}"
        )

    question_point_ids = await QuestionRepository.list_knowledge_point_ids_by_question_ids(
        db,
        question_ids=question_ids,
    )
    results: list[TestResultItem] = []
    answer_details: list[dict[str, object]] = []
    wrong_items: list[dict[str, object]] = []
    mastery_outcomes: list[KnowledgeMasteryAnswerOutcome] = []
    correct_count = 0

    for submitted in payload.answers:
        question = questions_by_id[submitted.question_id]
        linked_point_ids = question_point_ids.get(question.id, [])
        user_answer = _extract_submitted_answer(submitted, question)
        if question.question_type.value in OBJECTIVE_QUESTION_TYPES:
            correct_answer = _normalize_answer(question.correct_answer)
            ai_usage_service.clear_pending_traces()
            try:
                (
                    item_score,
                    is_correct,
                    item_analysis,
                    wrong_reason,
                    matched_points,
                    missing_points,
                    misconceptions,
                ) = _score_objective_answer(question, user_answer)
            finally:
                await ai_usage_service.record_pending_traces(
                    db,
                    user_id=user_id,
                    target_id=payload.target_id or question.target_id,
                    material_id=payload.material_id,
                )
        else:
            correct_answer = [
                str(answer).strip()
                for answer in question.correct_answer
                if str(answer).strip()
            ]
            ai_usage_service.clear_pending_traces()
            try:
                (
                    item_score,
                    is_correct,
                    item_analysis,
                    wrong_reason,
                    matched_points,
                    missing_points,
                    misconceptions,
                ) = _score_subjective_answer(question, user_answer)
            finally:
                await ai_usage_service.record_pending_traces(
                    db,
                    user_id=user_id,
                    target_id=payload.target_id or question.target_id,
                    material_id=payload.material_id,
                )
        if is_correct:
            correct_count += 1

        result = TestResultItem(
            question_id=question.id,
            knowledge_point_ids=linked_point_ids,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            score=item_score,
            analysis=item_analysis,
            matched_points=matched_points,
            missing_points=missing_points,
            misconceptions=misconceptions,
        )
        results.append(result)
        answer_details.append(result.model_dump())
        target_id = payload.target_id or question.target_id
        if target_id is not None and linked_point_ids:
            mastery_outcomes.append(
                KnowledgeMasteryAnswerOutcome(
                    target_id=target_id,
                    knowledge_point_ids=linked_point_ids,
                    is_correct=is_correct,
                    score=item_score,
                )
            )
        if not is_correct:
            wrong_items.append(
                {
                    "question_id": question.id,
                    "target_id": payload.target_id,
                    "material_id": payload.material_id,
                    "stem": question.stem,
                    "user_answer": user_answer,
                    "correct_answer": correct_answer,
                    "analysis": item_analysis,
                    "wrong_reason": wrong_reason
                    or _build_wrong_reason(question, user_answer),
                    "knowledge_points": [
                        str(point) for point in question.knowledge_points
                    ],
                    "knowledge_point_ids": linked_point_ids,
                }
            )

    total_count = len(payload.answers)
    wrong_count = total_count - correct_count
    accuracy = round(correct_count / total_count, 4)
    score = round(
        sum(float(result.score) for result in results) / total_count * 100,
        2,
    )

    record, _ = await TestRecordRepository.create_test_record(
        db,
        user_id=user_id,
        material_id=payload.material_id,
        target_id=payload.target_id,
        score=score,
        accuracy=accuracy,
        total_count=total_count,
        correct_count=correct_count,
        wrong_count=wrong_count,
        answer_details=answer_details,
    )
    await wrong_question_service.create_wrong_questions(
        db,
        user_id=user_id,
        test_record_id=record.id,
        wrong_items=wrong_items,
    )
    await knowledge_mastery_service.update_mastery_after_test(
        db,
        user_id=user_id,
        outcomes=mastery_outcomes,
    )

    return TestSubmitResponse(
        test_record_id=record.id,
        score=record.score,
        accuracy=record.accuracy,
        total_count=record.total_count,
        correct_count=record.correct_count,
        wrong_count=record.wrong_count,
        results=results,
        knowledge_point_summary=_build_knowledge_point_summary(results),
    )
