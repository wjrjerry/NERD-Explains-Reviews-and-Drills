from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.models.qa import QaRecord
from app.models.question import Question
from app.models.review_plan import ReviewPlan, ReviewPlanTask
from app.models.test_record import TestAnswerRecord, TestRecord
from app.models.wrong_question import WrongQuestion
from tests.concurrency_helpers import (
    api_ok,
    auth_headers,
    create_logged_in_user,
    create_study_target,
    env_int,
    no_server_error,
    run_concurrently,
    unique_name,
    upload_text_material,
)
from tests.test_db_concurrency_c06_c11 import _mark_material_parsed


async def _prepare_learning_context(client, async_session_factory):
    token, user, _username = await create_logged_in_user(client, prefix="learning_concurrency_user")
    headers = auth_headers(token)
    target = await create_study_target(client, headers=headers, title=unique_name("learning_target"))
    material = await upload_text_material(
        client,
        headers=headers,
        target_id=target["id"],
        auto_parse=False,
        text=(
            "# Learning Flow\n"
            "Requirements analysis, design reviews, testing, and deployment are all examinable concepts.\n"
            "Questions, QA, wrong-question reviews, and review plans should remain stable under concurrency.\n"
        ),
    )
    await _mark_material_parsed(async_session_factory, material["id"])
    return token, headers, user, target, material


async def _generate_questions(
    client,
    headers: dict[str, str],
    *,
    material_id: int,
    target_id: int | None = None,
    count: int = 4,
):
    if target_id is not None:
        graph_response = await client.post(
            "/knowledge-graphs/generate",
            json={
                "target_id": target_id,
                "material_id": None,
                "force_regenerate": False,
                "max_points": max(6, count * 2),
            },
            headers=headers,
        )
        assert api_ok(graph_response), graph_response.text

    payload = {
        "material_id": material_id,
        "question_types": ["single_choice"],
        "difficulty": "easy",
        "count": count,
    }
    if target_id is not None:
        payload["target_id"] = target_id
    response = await client.post("/questions/generate", json=payload, headers=headers)
    assert api_ok(response), response.text
    return response.json()["data"]["questions"]


async def _question_rows(async_session_factory, question_ids: list[int]) -> list[Question]:
    async with async_session_factory() as db:
        rows = list(
            (
                await db.execute(
                    select(Question).where(Question.id.in_(question_ids))
                )
            )
            .scalars()
            .all()
        )
    row_map = {row.id: row for row in rows}
    return [row_map[question_id] for question_id in question_ids]


def _build_submission_answers(rows: list[Question], *, wrong_index: int | None) -> list[dict[str, object]]:
    answers = []
    for index, row in enumerate(rows):
        if wrong_index is not None and index == wrong_index:
            answers.append({"question_id": row.id, "answer": ["__wrong__"]})
        else:
            answers.append({"question_id": row.id, "answer": list(row.correct_answer)})
    return answers


async def _create_wrong_questions(client, async_session_factory):
    _token, headers, user, target, material = await _prepare_learning_context(client, async_session_factory)
    generated = await _generate_questions(
        client,
        headers,
        material_id=material["id"],
        target_id=target["id"],
        count=3,
    )
    rows = await _question_rows(async_session_factory, [item["id"] for item in generated])
    submit_response = await client.post(
        "/tests/submit",
        json={
            "material_id": material["id"],
            "target_id": target["id"],
            "answers": _build_submission_answers(rows, wrong_index=0),
        },
        headers=headers,
    )
    assert api_ok(submit_response), submit_response.text
    wrong_response = await client.get(
        f"/wrong-questions?target_id={target['id']}&material_id={material['id']}",
        headers=headers,
    )
    assert api_ok(wrong_response), wrong_response.text
    items = wrong_response.json()["data"]["items"]
    assert items
    return headers, user, target, material, items


@pytest.mark.asyncio
async def test_db_c18_concurrent_qa_records_count_matches(client, async_session_factory):
    concurrency = env_int("DB_C18_CONCURRENCY", 80)
    _token, headers, user, target, material = await _prepare_learning_context(client, async_session_factory)
    async with async_session_factory() as db:
        before_count = await db.scalar(
            select(func.count()).select_from(QaRecord).where(
                QaRecord.user_id == user["id"],
                QaRecord.material_id == material["id"],
            )
        )

    async def ask(index: int):
        return await client.post(
            "/qa/ask",
            json={
                "material_id": material["id"],
                "target_id": target["id"],
                "question": f"What is concurrency checkpoint {index}?",
            },
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C18",
        module="qa record insert/history",
        code_paths=[
            "app/routers/qa.py",
            "app/services/qa_service.py",
            "app/repositories/qa_repository.py",
            "app/models/qa.py",
            "app/models/ai_call_log.py",
        ],
        concurrency=concurrency,
        operation=ask,
        is_success=api_ok,
        notes="Concurrent QA requests should append one qa_record each and remain visible in history.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        after_count = await db.scalar(
            select(func.count()).select_from(QaRecord).where(
                QaRecord.user_id == user["id"],
                QaRecord.material_id == material["id"],
            )
        )
    assert after_count - before_count == concurrency


@pytest.mark.asyncio
async def test_db_c19_concurrent_question_generation_counts_match(client, async_session_factory):
    requested_counts = [2, 3, 2, 3]
    concurrency = len(requested_counts)
    _token, headers, user, _target, material = await _prepare_learning_context(client, async_session_factory)

    async def generate(index: int):
        return await client.post(
            "/questions/generate",
            json={
                "material_id": material["id"],
                "question_types": ["single_choice"],
                "difficulty": "medium",
                "count": requested_counts[index],
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C19",
        module="question generation insert/link",
        code_paths=[
            "app/routers/questions.py",
            "app/services/question_service.py",
            "app/repositories/question_repository.py",
            "app/models/question.py",
        ],
        concurrency=concurrency,
        operation=generate,
        is_success=api_ok,
        notes="Concurrent question generation should persist the requested number of questions per request.",
    )

    assert report.success_count == concurrency
    returned_ids: list[int] = []
    for response, expected in zip(responses, requested_counts, strict=True):
        assert not isinstance(response, Exception)
        assert api_ok(response), response.text
        questions = response.json()["data"]["questions"]
        assert len(questions) == expected
        returned_ids.extend(int(question["id"]) for question in questions)

    async with async_session_factory() as db:
        persisted_count = await db.scalar(
            select(func.count()).select_from(Question).where(
                Question.user_id == user["id"],
                Question.id.in_(returned_ids),
            )
        )
    assert persisted_count == sum(requested_counts)
    assert len(returned_ids) == len(set(returned_ids))


@pytest.mark.asyncio
async def test_db_c20_concurrent_test_submit_creates_complete_records(client, async_session_factory):
    concurrency = env_int("DB_C20_CONCURRENCY", 30)
    _token, headers, user, target, material = await _prepare_learning_context(client, async_session_factory)
    generated = await _generate_questions(
        client,
        headers,
        material_id=material["id"],
        target_id=target["id"],
        count=4,
    )
    rows = await _question_rows(async_session_factory, [item["id"] for item in generated])

    async with async_session_factory() as db:
        before_test_records = await db.scalar(
            select(func.count()).select_from(TestRecord).where(TestRecord.user_id == user["id"])
        )
        before_answer_records = await db.scalar(
            select(func.count()).select_from(TestAnswerRecord).where(TestAnswerRecord.user_id == user["id"])
        )
        before_wrong_questions = await db.scalar(
            select(func.count()).select_from(WrongQuestion).where(WrongQuestion.user_id == user["id"])
        )

    async def submit(index: int):
        return await client.post(
            "/tests/submit",
            json={
                "material_id": material["id"],
                "target_id": target["id"],
                "answers": _build_submission_answers(rows, wrong_index=index % len(rows)),
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C20",
        module="test record, answer record, wrong-question creation",
        code_paths=[
            "app/routers/tests.py",
            "app/services/test_service.py",
            "app/repositories/test_record_repository.py",
            "app/repositories/wrong_question_repository.py",
            "app/models/test_record.py",
            "app/models/wrong_question.py",
        ],
        concurrency=concurrency,
        operation=submit,
        is_success=api_ok,
        notes="Concurrent submissions should persist one test_record and a complete answer set per request.",
    )

    assert report.success_count == concurrency
    for response in responses:
        assert not isinstance(response, Exception)
        assert api_ok(response), response.text
        assert response.json()["data"]["total_count"] == len(rows)

    async with async_session_factory() as db:
        after_test_records = await db.scalar(
            select(func.count()).select_from(TestRecord).where(TestRecord.user_id == user["id"])
        )
        after_answer_records = await db.scalar(
            select(func.count()).select_from(TestAnswerRecord).where(TestAnswerRecord.user_id == user["id"])
        )
        after_wrong_questions = await db.scalar(
            select(func.count()).select_from(WrongQuestion).where(WrongQuestion.user_id == user["id"])
        )

    assert after_test_records - before_test_records == concurrency
    assert after_answer_records - before_answer_records == concurrency * len(rows)
    assert after_wrong_questions - before_wrong_questions == concurrency


@pytest.mark.asyncio
async def test_db_c21_concurrent_wrong_question_mastery_updates_stay_legal(client, async_session_factory):
    concurrency = env_int("DB_C21_CONCURRENCY", 80)
    headers, user, target, material, wrong_items = await _create_wrong_questions(client, async_session_factory)
    wrong_id = int(wrong_items[0]["id"])
    statuses = ["reviewing", "mastered", "unmastered", "reviewing"]

    async def update(index: int):
        return await client.patch(
            f"/wrong-questions/{wrong_id}/mastery",
            json={"mastery_status": statuses[index % len(statuses)]},
            headers=headers,
        )

    report, _responses = await run_concurrently(
        case_id="DB-C21",
        module="wrong-question mastery/review counter",
        code_paths=[
            "app/routers/wrong_questions.py",
            "app/services/wrong_question_service.py",
            "app/repositories/wrong_question_repository.py",
            "app/models/wrong_question.py",
        ],
        concurrency=concurrency,
        operation=update,
        is_success=no_server_error,
        notes="Concurrent mastery updates should keep one readable wrong_question row with valid status fields.",
    )

    assert report.success_count == concurrency
    async with async_session_factory() as db:
        row = await db.scalar(
            select(WrongQuestion).where(
                WrongQuestion.id == wrong_id,
                WrongQuestion.user_id == user["id"],
                WrongQuestion.target_id == target["id"],
                WrongQuestion.material_id == material["id"],
            )
        )
    assert row is not None
    assert row.mastery_status.value in {"unmastered", "reviewing", "mastered"}
    assert row.review_count >= 1
    assert row.last_reviewed_at is not None


@pytest.mark.asyncio
async def test_db_c22_review_queue_mixed_read_write_no_5xx(client, async_session_factory):
    writer_count = env_int("DB_C22_WRITERS", 30)
    reader_count = env_int("DB_C22_READERS", 200)
    concurrency = writer_count + reader_count
    headers, _user, target, _material, wrong_items = await _create_wrong_questions(client, async_session_factory)
    wrong_ids = [int(item["id"]) for item in wrong_items]

    async def read_or_write(index: int):
        if index < reader_count:
            return await client.get(
                f"/wrong-questions/review-queue?target_id={target['id']}&limit=10",
                headers=headers,
            )
        wrong_id = wrong_ids[(index - reader_count) % len(wrong_ids)]
        return await client.patch(
            f"/wrong-questions/{wrong_id}/mastery",
            json={"mastery_status": "reviewing"},
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C22",
        module="wrong-question review queue mixed load",
        code_paths=[
            "app/routers/wrong_questions.py",
            "app/services/wrong_question_service.py",
            "app/repositories/wrong_question_repository.py",
            "app/models/wrong_question.py",
        ],
        concurrency=concurrency,
        operation=read_or_write,
        is_success=no_server_error,
        notes=f"{reader_count} queue reads race with {writer_count} mastery writes on the same wrong-question set.",
    )

    assert report.success_count == concurrency
    queue_responses = [
        response
        for response in responses[:reader_count]
        if not isinstance(response, Exception) and getattr(response, "status_code", 500) == 200
    ]
    assert queue_responses
    for response in queue_responses:
        returned_ids = {
            int(item["id"])
            for item in response.json()["data"]
        }
        assert returned_ids.issubset(set(wrong_ids))


@pytest.mark.asyncio
async def test_db_c23_concurrent_review_plan_generation_persists_complete_tasks(client, async_session_factory):
    concurrency = env_int("DB_C23_CONCURRENCY", 40)
    _token, headers, user, target, _material = await _prepare_learning_context(client, async_session_factory)
    start_date = date.today()
    end_date = start_date + timedelta(days=2)
    expected_task_count = 3

    async with async_session_factory() as db:
        before_plans = await db.scalar(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user["id"],
                ReviewPlan.target_id == target["id"],
            )
        )
        before_tasks = await db.scalar(
            select(func.count())
            .select_from(ReviewPlanTask)
            .join(ReviewPlan, ReviewPlan.id == ReviewPlanTask.plan_id)
            .where(
                ReviewPlan.user_id == user["id"],
                ReviewPlan.target_id == target["id"],
            )
        )

    async def generate(_index: int):
        return await client.post(
            "/review-plans/generate",
            json={
                "target_id": target["id"],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C23",
        module="review plan and review plan task creation",
        code_paths=[
            "app/routers/review_plans.py",
            "app/services/review_plan_service.py",
            "app/repositories/review_plan_repository.py",
            "app/models/review_plan.py",
        ],
        concurrency=concurrency,
        operation=generate,
        is_success=api_ok,
        notes="Concurrent review-plan generation should create a full task set for each saved plan.",
    )

    assert report.success_count == concurrency
    for response in responses:
        assert not isinstance(response, Exception)
        assert api_ok(response), response.text
        assert len(response.json()["data"]["tasks"]) == expected_task_count

    async with async_session_factory() as db:
        after_plans = await db.scalar(
            select(func.count()).select_from(ReviewPlan).where(
                ReviewPlan.user_id == user["id"],
                ReviewPlan.target_id == target["id"],
            )
        )
        after_tasks = await db.scalar(
            select(func.count())
            .select_from(ReviewPlanTask)
            .join(ReviewPlan, ReviewPlan.id == ReviewPlanTask.plan_id)
            .where(
                ReviewPlan.user_id == user["id"],
                ReviewPlan.target_id == target["id"],
            )
        )

    assert after_plans - before_plans == concurrency
    assert after_tasks - before_tasks == concurrency * expected_task_count


@pytest.mark.asyncio
async def test_db_c24_concurrent_review_task_toggle_stays_boolean(client, async_session_factory):
    concurrency = env_int("DB_C24_CONCURRENCY", 100)
    _token, headers, user, target, _material = await _prepare_learning_context(client, async_session_factory)
    today = date.today().isoformat()
    create_response = await client.post(
        "/review-plans/generate",
        json={
            "target_id": target["id"],
            "start_date": today,
            "end_date": today,
        },
        headers=headers,
    )
    assert api_ok(create_response), create_response.text
    task_id = int(create_response.json()["data"]["tasks"][0]["id"])

    async def toggle(index: int):
        return await client.patch(
            f"/review-plans/tasks/{task_id}",
            json={"completed": index % 2 == 0},
            headers=headers,
        )

    report, responses = await run_concurrently(
        case_id="DB-C24",
        module="review plan task completion toggle",
        code_paths=[
            "app/routers/review_plans.py",
            "app/services/review_plan_service.py",
            "app/repositories/review_plan_repository.py",
            "app/models/review_plan.py",
        ],
        concurrency=concurrency,
        operation=toggle,
        is_success=api_ok,
        notes="Concurrent task complete/cancel requests should leave a boolean final task state and avoid 5xx responses.",
    )

    assert report.success_count == concurrency
    for response in responses:
        assert not isinstance(response, Exception)
        assert api_ok(response), response.text
        assert isinstance(response.json()["data"]["completed"], bool)

    async with async_session_factory() as db:
        task = await db.scalar(
            select(ReviewPlanTask)
            .join(ReviewPlan, ReviewPlan.id == ReviewPlanTask.plan_id)
            .where(
                ReviewPlanTask.id == task_id,
                ReviewPlan.user_id == user["id"],
            )
        )
    assert task is not None
    assert isinstance(task.completed, bool)
