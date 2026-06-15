"""Business service for review plan generation."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.review_plan import ReviewPlan
from app.models.study_target import StudyTarget
from app.models.knowledge_point import MasteryStatus as KnowledgeMasteryStatus
from app.models.wrong_question import MasteryStatus
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.repositories.review_plan_repository import ReviewPlanRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.repositories.wrong_question_repository import WrongQuestionRepository
from app.schemas.review_plan import (
    ReviewPlanGenerateRequest,
    ReviewPlanResponse,
    ReviewPlanTask,
)
from app.services import ai_service, ai_usage_service


MAX_PLAN_DAYS = 60


def _date_range(start: date, end: date) -> list[date]:
    """Return every date in the inclusive range."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _resolve_plan_dates(
    payload: ReviewPlanGenerateRequest,
    target: StudyTarget,
) -> tuple[date, date]:
    """Resolve start/end dates from request and target exam date."""
    start = payload.start_date or date.today()
    end = payload.end_date or target.exam_date or (start + timedelta(days=6))

    if end < start:
        raise ValueError("end_date cannot be earlier than start_date")
    if (end - start).days + 1 > MAX_PLAN_DAYS:
        raise ValueError(f"review plan cannot exceed {MAX_PLAN_DAYS} days")

    return start, end


def _to_response(plan: ReviewPlan) -> ReviewPlanResponse:
    """Map ORM plan to API response."""
    return ReviewPlanResponse(
        id=plan.id,
        target_id=plan.target_id,
        title=plan.title,
        start_date=plan.start_date,
        end_date=plan.end_date,
        summary=plan.summary,
        tasks=[
            ReviewPlanTask(
                id=task.id,
                date=task.task_date,
                title=task.title,
                content=task.content,
                material_id=task.material_id,
                wrong_question_id=task.wrong_question_id,
                knowledge_point_id=task.knowledge_point_id,
                completed=task.completed,
            )
            for task in plan.tasks
        ],
    )


def _build_focus_items(wrong_questions) -> list[dict[str, object]]:
    """Build prioritized focus items from wrong questions."""
    point_counter: Counter[str] = Counter()
    first_wrong_by_point = {}
    material_by_point = {}

    for wrong in wrong_questions:
        weight = 2 if wrong.mastery_status == MasteryStatus.unmastered else 1
        points = wrong.knowledge_points or ["综合复习"]
        for point in points:
            normalized = str(point).strip()
            if not normalized:
                continue
            point_counter[normalized] += weight
            first_wrong_by_point.setdefault(normalized, wrong.id)
            material_by_point.setdefault(normalized, wrong.material_id)

    if not point_counter:
        return []

    return [
        {
            "knowledge_point": point,
            "weight": count,
            "wrong_question_id": first_wrong_by_point.get(point),
            "material_id": material_by_point.get(point),
        }
        for point, count in point_counter.most_common()
    ]


async def _build_knowledge_focus_items(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int,
    wrong_questions,
) -> list[dict[str, object]]:
    """Build prioritized focus items from graph mastery, wrongs, and evidence."""
    points = await KnowledgeGraphRepository.list_points_by_target(
        db,
        user_id=user_id,
        target_id=target_id,
    )
    if not points:
        return _build_focus_items(wrong_questions)

    mastery_map = await KnowledgeGraphRepository.list_mastery_by_point_ids(
        db,
        user_id=user_id,
        point_ids=[point.id for point in points],
    )
    material_links = await KnowledgeGraphRepository.list_material_links_by_point_ids(
        db,
        point_ids=[point.id for point in points],
    )
    wrong_link_map = await WrongQuestionRepository.list_knowledge_point_ids_by_wrong_question_ids(
        db,
        wrong_question_ids=[wrong.id for wrong in wrong_questions],
    )

    first_wrong_by_point: dict[int, int] = {}
    wrong_count_by_point: Counter[int] = Counter()
    for wrong in wrong_questions:
        for point_id in wrong_link_map.get(wrong.id, []):
            wrong_count_by_point[point_id] += 2 if wrong.mastery_status == MasteryStatus.unmastered else 1
            first_wrong_by_point.setdefault(point_id, wrong.id)

    items: list[dict[str, object]] = []
    for point in points:
        mastery = mastery_map.get(point.id)
        answered_count = mastery.answered_count if mastery else 0
        wrong_count = mastery.wrong_count if mastery else 0
        accuracy = mastery.accuracy if mastery else 0.0
        status = mastery.mastery_status if mastery else KnowledgeMasteryStatus.unlearned
        material_id = None
        links = material_links.get(point.id, [])
        if links:
            material_id = links[0].material_id

        weakness = 1.0 - accuracy
        if status == KnowledgeMasteryStatus.weak:
            weakness += 0.5
        elif status == KnowledgeMasteryStatus.unlearned:
            weakness += 0.35
        weakness += min(wrong_count_by_point.get(point.id, 0) + wrong_count, 6) * 0.08
        weight = round(weakness + point.importance_weight, 4)

        items.append(
            {
                "knowledge_point_id": point.id,
                "knowledge_point": point.name,
                "weight": weight,
                "mastery_status": status.value,
                "accuracy": accuracy,
                "answered_count": answered_count,
                "wrong_count": wrong_count,
                "next_review_at": (
                    mastery.next_review_at.isoformat()
                    if mastery and mastery.next_review_at
                    else None
                ),
                "wrong_question_id": first_wrong_by_point.get(point.id),
                "material_id": material_id,
            }
        )

    return sorted(
        items,
        key=lambda item: (
            float(item["weight"]),
            int(item.get("wrong_count") or 0),
            int(item.get("answered_count") or 0) == 0,
        ),
        reverse=True,
    )


def _build_tasks(
    *,
    target: StudyTarget,
    dates: list[date],
    focus_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Generate daily review tasks from focus items and target metadata."""
    tasks: list[dict[str, object]] = []
    subject = target.subject or target.title

    if not focus_items:
        focus_items = [
            {
                "knowledge_point": subject,
                "weight": 1,
                "knowledge_point_id": None,
                "wrong_question_id": None,
                "material_id": None,
            }
        ]

    for index, task_date in enumerate(dates):
        focus = focus_items[index % len(focus_items)]
        point = str(focus["knowledge_point"])
        is_last_day = index == len(dates) - 1

        if is_last_day and len(dates) >= 3:
            title = f"{subject} 综合回顾"
            content = (
                "回顾本轮复习中的错题、主观题反馈和核心知识点，"
                "整理仍不熟悉的概念，并完成一次简短自测。"
            )
        else:
            title = f"复习 {point}"
            content = (
                f"重点复习「{point}」，先阅读相关资料，再回看对应错题或测试反馈；"
                "最后用自己的话总结本知识点的定义、作用和易错点。"
            )

        tasks.append(
            {
                "date": task_date,
                "title": title,
                "content": content,
                "knowledge_point_id": focus.get("knowledge_point_id"),
                "material_id": focus.get("material_id"),
                "wrong_question_id": focus.get("wrong_question_id"),
            }
        )

    return tasks


def _safe_int(value: object) -> int | None:
    """Convert a model-returned ID to int if possible."""
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_ai_review_plan(
    *,
    raw_plan: dict[str, object],
    dates: list[date],
    focus_items: list[dict[str, object]],
    fallback_tasks: list[dict[str, object]],
    fallback_title: str,
    fallback_summary: str,
) -> tuple[str, str, list[dict[str, object]]]:
    """Validate AI-generated review plan and normalize it for persistence."""
    allowed_dates = {item.isoformat(): item for item in dates}
    allowed_material_ids = {
        int(item["material_id"])
        for item in focus_items
        if item.get("material_id") is not None
    }
    allowed_wrong_question_ids = {
        int(item["wrong_question_id"])
        for item in focus_items
        if item.get("wrong_question_id") is not None
    }
    allowed_knowledge_point_ids = {
        int(item["knowledge_point_id"])
        for item in focus_items
        if item.get("knowledge_point_id") is not None
    }
    raw_tasks = raw_plan.get("tasks")
    if not isinstance(raw_tasks, list):
        return fallback_title, fallback_summary, fallback_tasks

    task_by_date: dict[str, dict[str, object]] = {}
    for raw_task in raw_tasks:
        if not isinstance(raw_task, dict):
            continue
        raw_date = str(raw_task.get("date", "")).strip()
        if raw_date not in allowed_dates or raw_date in task_by_date:
            continue

        material_id = _safe_int(raw_task.get("material_id"))
        wrong_question_id = _safe_int(raw_task.get("wrong_question_id"))
        knowledge_point_id = _safe_int(raw_task.get("knowledge_point_id"))
        normalized_material_id = (
            material_id
            if material_id is not None and material_id in allowed_material_ids
            else None
        )
        normalized_wrong_question_id = (
            wrong_question_id
            if wrong_question_id is not None
            and wrong_question_id in allowed_wrong_question_ids
            else None
        )
        normalized_knowledge_point_id = (
            knowledge_point_id
            if knowledge_point_id is not None
            and knowledge_point_id in allowed_knowledge_point_ids
            else None
        )
        title = str(raw_task.get("title", "")).strip()
        content = str(raw_task.get("content", "")).strip()
        if not title or not content:
            continue

        task_by_date[raw_date] = {
            "date": allowed_dates[raw_date],
            "title": title,
            "content": content,
            "knowledge_point_id": normalized_knowledge_point_id,
            "material_id": normalized_material_id,
            "wrong_question_id": normalized_wrong_question_id,
        }

    if len(task_by_date) != len(dates):
        return fallback_title, fallback_summary, fallback_tasks

    title = str(raw_plan.get("title", "")).strip() or fallback_title
    summary = str(raw_plan.get("summary", "")).strip() or fallback_summary
    tasks = [task_by_date[item.isoformat()] for item in dates]
    return title, summary, tasks


async def generate_review_plan(
    db: AsyncSession,
    payload: ReviewPlanGenerateRequest,
    *,
    user_id: int,
) -> ReviewPlanResponse:
    """Generate and save a review plan for one study target."""
    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=payload.target_id,
        user_id=user_id,
    )
    if target is None:
        raise LookupError("Study target not found.")

    start_date, end_date = _resolve_plan_dates(payload, target)
    dates = _date_range(start_date, end_date)
    wrong_questions, _ = await WrongQuestionRepository.list_wrong_questions(
        db,
        user_id=user_id,
        target_id=target.id,
        page=1,
        page_size=200,
    )
    focus_items = await _build_knowledge_focus_items(
        db,
        user_id=user_id,
        target_id=target.id,
        wrong_questions=wrong_questions,
    )
    fallback_tasks = _build_tasks(target=target, dates=dates, focus_items=focus_items)
    weak_points = [str(item["knowledge_point"]) for item in focus_items[:5]]
    if weak_points:
        fallback_summary = "根据错题本中的薄弱知识点生成，优先复习：" + "、".join(weak_points)
    else:
        fallback_summary = "当前目标下错题较少，已生成通用资料回顾与综合自测计划。"

    fallback_title = f"{target.title} 复习计划"
    title = fallback_title
    summary = fallback_summary
    tasks = fallback_tasks
    if settings.ai_provider != "mock":
        ai_usage_service.clear_pending_traces()
        try:
            raw_plan = ai_service.generate_review_plan(
                target_title=target.title,
                subject=target.subject,
                exam_date=target.exam_date.isoformat() if target.exam_date else None,
                review_goal=target.review_goal,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                dates=[item.isoformat() for item in dates],
                focus_items=focus_items,
            )
        finally:
            await ai_usage_service.record_pending_traces(
                db,
                user_id=user_id,
                target_id=target.id,
                material_id=None,
            )
        title, summary, tasks = _normalize_ai_review_plan(
            raw_plan=raw_plan,
            dates=dates,
            focus_items=focus_items,
            fallback_tasks=fallback_tasks,
            fallback_title=fallback_title,
            fallback_summary=fallback_summary,
        )

    plan = await ReviewPlanRepository.create_review_plan(
        db,
        user_id=user_id,
        target_id=target.id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        summary=summary,
        tasks=tasks,
    )
    return _to_response(plan)


async def list_review_plans(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ReviewPlanResponse], int]:
    """Return paginated review plans for one user."""
    plans, total = await ReviewPlanRepository.list_review_plans(
        db,
        user_id=user_id,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )
    return [_to_response(plan) for plan in plans], total
