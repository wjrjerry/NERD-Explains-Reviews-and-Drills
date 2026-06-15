"""Export service for Markdown and Anki-compatible CSV downloads."""

from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeExtractionScope
from app.models.question import Question
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.review_plan_repository import ReviewPlanRepository
from app.repositories.study_target_repository import StudyTargetRepository
from app.repositories.wrong_question_repository import WrongQuestionRepository


def _line(value: object | None, fallback: str = "-") -> str:
    """Return a clean single-line string for Markdown output."""
    text = str(value or "").strip()
    return text.replace("\r", "").replace("\n", " ") if text else fallback


def _list_lines(items: list[str] | object, *, empty: str = "- 暂无") -> list[str]:
    """Render a list of strings as Markdown bullets."""
    if not isinstance(items, list):
        return [empty]
    rendered = [f"- {_line(item)}" for item in items if str(item or "").strip()]
    return rendered or [empty]


def _answer_text(answers: list[str] | object) -> str:
    """Render answer arrays into compact display text."""
    if not isinstance(answers, list):
        return ""
    return "、".join(str(item).strip() for item in answers if str(item).strip())


def _question_options_text(question: Question) -> str:
    """Render objective question options for CSV back side."""
    lines: list[str] = []
    for option in question.options:
        key = str(option.get("key", "")).strip()
        text = str(option.get("text", "")).strip()
        analysis = str(option.get("analysis", "")).strip()
        if key and text:
            lines.append(f"{key}. {text}")
        if analysis:
            lines.append(f"选项{key}解析：{analysis}")
    return "\n".join(lines)


def _tags(*parts: object | None) -> str:
    """Build an Anki tag string from target/material/knowledge point labels."""
    tags: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, list):
            values = part
        else:
            values = [part]
        for value in values:
            normalized = str(value or "").strip().replace(" ", "_")
            if normalized:
                tags.append(normalized)
    return " ".join(dict.fromkeys(tags))


async def export_wrong_questions_markdown(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int | None,
    material_id: int | None,
) -> str:
    """Export wrong questions as Markdown."""
    wrong_questions, total = await WrongQuestionRepository.list_wrong_questions(
        db,
        user_id=user_id,
        target_id=target_id,
        material_id=material_id,
        page=1,
        page_size=1000,
    )
    title = "错题本导出"
    if target_id is not None:
        target = await StudyTargetRepository.get_by_id(
            db,
            target_id=target_id,
            user_id=user_id,
        )
        if target is None:
            raise LookupError("Study target not found.")
        title = f"{target.title} 错题本"

    lines = [
        f"# {title}",
        "",
        f"- 错题数量：{total}",
        f"- 目标ID：{target_id if target_id is not None else '全部'}",
        f"- 资料ID：{material_id if material_id is not None else '全部'}",
        "",
    ]

    if not wrong_questions:
        lines.append("暂无错题。")
        return "\n".join(lines)

    for index, wrong in enumerate(wrong_questions, start=1):
        lines.extend(
            [
                f"## {index}. {_line(wrong.stem)}",
                "",
                f"- 掌握状态：{wrong.mastery_status.value}",
                f"- 资料ID：{wrong.material_id}",
                f"- 题目ID：{wrong.question_id}",
                f"- 知识点：{_answer_text(wrong.knowledge_points) or '暂无'}",
                "",
                f"**我的答案：** {_answer_text(wrong.user_answer) or '未作答'}",
                "",
                f"**正确答案：** {_answer_text(wrong.correct_answer) or '暂无'}",
                "",
                f"**解析：** {_line(wrong.analysis)}",
                "",
                f"**错误原因：** {_line(wrong.wrong_reason)}",
                "",
            ]
        )

    return "\n".join(lines)


async def export_review_plan_markdown(
    db: AsyncSession,
    *,
    user_id: int,
    plan_id: int,
) -> str:
    """Export one review plan as Markdown."""
    plan = await ReviewPlanRepository.get_by_id(db, user_id=user_id, plan_id=plan_id)
    if plan is None:
        raise LookupError("Review plan not found.")

    lines = [
        f"# {plan.title}",
        "",
        f"- 计划周期：{plan.start_date.isoformat()} 至 {plan.end_date.isoformat()}",
        f"- 目标ID：{plan.target_id}",
        "",
        "## 计划摘要",
        "",
        _line(plan.summary),
        "",
        "## 每日任务",
        "",
    ]
    for task in plan.tasks:
        lines.extend(
            [
                f"### {task.task_date.isoformat()} {_line(task.title)}",
                "",
                _line(task.content),
                "",
                f"- 知识点ID：{task.knowledge_point_id if task.knowledge_point_id is not None else '无'}",
                f"- 资料ID：{task.material_id if task.material_id is not None else '无'}",
                f"- 错题ID：{task.wrong_question_id if task.wrong_question_id is not None else '无'}",
                f"- 完成状态：{'已完成' if task.completed else '未完成'}",
                "",
            ]
        )
    return "\n".join(lines)


async def export_knowledge_summary_markdown(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int,
) -> str:
    """Export target-level and material-level knowledge extraction as Markdown."""
    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=target_id,
        user_id=user_id,
    )
    if target is None:
        raise LookupError("Study target not found.")

    target_extraction = await KnowledgeRepository.get_latest(
        db,
        user_id=user_id,
        scope=KnowledgeExtractionScope.target,
        target_id=target_id,
    )
    material_extractions = await KnowledgeRepository.list_latest_material_extractions_by_target(
        db,
        user_id=user_id,
        target_id=target_id,
    )
    materials = await MaterialRepository.list_parsed_by_target(
        db,
        user_id=user_id,
        target_id=target_id,
    )
    material_name_by_id = {
        material.id: material.original_filename for material in materials
    }
    points = await KnowledgeGraphRepository.list_points_by_target(
        db,
        user_id=user_id,
        target_id=target_id,
    )
    mastery_map = await KnowledgeGraphRepository.list_mastery_by_point_ids(
        db,
        user_id=user_id,
        point_ids=[point.id for point in points],
    )
    material_links = await KnowledgeGraphRepository.list_material_links_by_point_ids(
        db,
        point_ids=[point.id for point in points],
    )

    lines = [
        f"# {target.title} 知识提炼导出",
        "",
        f"- 目标ID：{target.id}",
        f"- 科目：{_line(target.subject)}",
        f"- 目标类型：{target.target_type.value}",
        "",
    ]

    if target_extraction is None:
        lines.extend(["## 目标级知识提炼", "", "暂无目标级知识提炼结果。", ""])
    else:
        lines.extend(
            [
                "## 目标级知识提炼",
                "",
                f"**摘要：** {_line(target_extraction.summary)}",
                "",
                "### 大纲",
                *_list_lines(target_extraction.outline),
                "",
                "### 关键词",
                *_list_lines(target_extraction.keywords),
                "",
                "### 核心知识点",
                *_list_lines(target_extraction.key_points),
                "",
                "### 备考重点",
                *_list_lines(target_extraction.exam_points),
                "",
            ]
        )

    lines.extend(["## 知识图谱与掌握度", ""])
    if not points:
        lines.extend(["暂无知识图谱节点。", ""])
    for point in points:
        mastery = mastery_map.get(point.id)
        links = material_links.get(point.id, [])
        evidence = "；".join(
            f"资料{link.material_id}: {_line(link.evidence_text)}" for link in links[:3]
        )
        lines.extend(
            [
                f"### {point.name}",
                "",
                f"- 知识点ID：{point.id}",
                f"- 层级：{point.level}",
                f"- 重要度：{point.importance_weight:.2f}",
                f"- 掌握状态：{mastery.mastery_status.value if mastery else 'unlearned'}",
                f"- 掌握分：{mastery.mastery_score if mastery else 0.0}",
                f"- 正确率：{mastery.accuracy if mastery else 0.0}",
                f"- 练习次数：{mastery.answered_count if mastery else 0}",
                f"- 错题次数：{mastery.wrong_count if mastery else 0}",
                f"- 说明：{_line(point.description)}",
                f"- 资料证据：{evidence or '暂无'}",
                "",
            ]
        )

    lines.extend(["## 资料级知识提炼", ""])
    if not material_extractions:
        lines.extend(["暂无资料级知识提炼结果。", ""])
    for extraction in material_extractions:
        material_name = material_name_by_id.get(
            extraction.material_id or -1,
            f"资料 {extraction.material_id}",
        )
        lines.extend(
            [
                f"### {material_name}",
                "",
                f"- 资料ID：{extraction.material_id}",
                f"- 生成时间：{extraction.created_at.isoformat()}",
                "",
                f"**摘要：** {_line(extraction.summary)}",
                "",
                "**大纲：**",
                *_list_lines(extraction.outline),
                "",
                "**关键词：**",
                *_list_lines(extraction.keywords),
                "",
                "**核心要点：**",
                *_list_lines(extraction.key_points),
                "",
                "**备考重点：**",
                *_list_lines(extraction.exam_points),
                "",
            ]
        )

    return "\n".join(lines)


async def export_anki_csv(
    db: AsyncSession,
    *,
    user_id: int,
    target_id: int,
) -> str:
    """Export generated questions under one target as Anki-compatible CSV."""
    target = await StudyTargetRepository.get_by_id(
        db,
        target_id=target_id,
        user_id=user_id,
    )
    if target is None:
        raise LookupError("Study target not found.")

    questions = await QuestionRepository.list_by_target(
        db,
        user_id=user_id,
        target_id=target_id,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["front", "back", "tags"])
    for question in questions:
        options = _question_options_text(question)
        correct_answer = _answer_text(question.correct_answer)
        knowledge_points = [
            str(point).strip()
            for point in question.knowledge_points
            if str(point).strip()
        ]
        back_parts = [
            options,
            f"正确答案：{correct_answer}" if correct_answer else "",
            f"解析：{question.analysis}",
            f"来源资料ID：{question.material_id}",
        ]
        writer.writerow(
            [
                question.stem,
                "\n\n".join(part for part in back_parts if part),
                _tags(target.title, question.difficulty.value, question.question_type.value, knowledge_points),
            ]
        )

    return output.getvalue()
