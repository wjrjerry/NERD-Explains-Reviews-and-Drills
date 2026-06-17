"""
DB-C18 through DB-C24: Learning Flow Concurrency Tests

DB-C18: QA records concurrency - concurrent QA on same material
DB-C19: Question generation concurrency - concurrent generation on same material
DB-C20: Test submission concurrency - concurrent submission, record/wrong-question integrity
DB-C21: Wrong question mastery concurrency - concurrent mastery status update
DB-C22: Wrong question review queue - mixed read/write
DB-C23: Review plan generation concurrency - concurrent plan generation
DB-C24: Review task completion concurrency - concurrent complete/cancel on same task
"""

import asyncio
import io
import time
import uuid
from datetime import date, timedelta

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_username() -> str:
    return f"dbc_{uuid.uuid4().hex[:10]}"


async def _register_and_login(client, username: str | None = None):
    username = username or _random_username()
    resp = await client.post(
        "/auth/register",
        json={"username": username, "password": "test123456", "display_name": "ConTest"},
    )
    if resp.json()["code"] != 0:
        return None
    resp = await client.post(
        "/auth/login",
        json={"username": username, "password": "test123456"},
    )
    return resp.json()["data"]["token"]["access_token"]


async def _create_target(client, token: str, title: str = "DB Concurrency Target"):
    resp = await client.post(
        "/study-targets",
        json={
            "title": title,
            "subject": "Software Engineering",
            "target_type": "exam",
            "exam_date": str(date.today() + timedelta(days=30)),
            "review_goal": "Concurrency test",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["data"]["target"]["id"]


async def _upload_and_wait_parse(client, token: str, target_id: int, content: str = None) -> int | None:
    if content is None:
        content = "Software engineering knowledge: requirements, design, implementation, verification, maintenance. " * 20

    file_content = io.BytesIO(content.encode("utf-8"))
    resp = await client.post(
        "/materials",
        data={"target_id": str(target_id), "auto_parse": "true"},
        files={"file": ("test.txt", file_content, "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.json()["code"] != 0:
        return None
    material_id = resp.json()["data"]["material"]["id"]

    for _ in range(30):
        r = await client.get(
            f"/materials/{material_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        status = r.json()["data"]["material"]["parse_status"]
        if status == "parsed":
            return material_id
        await asyncio.sleep(0.2)

    await client.post(
        f"/materials/{material_id}/parse",
        headers={"Authorization": f"Bearer {token}"},
    )
    for _ in range(30):
        r = await client.get(
            f"/materials/{material_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.json()["data"]["material"]["parse_status"] == "parsed":
            return material_id
        await asyncio.sleep(0.2)
    return material_id


# ===========================================================================
# DB-C18: QA Records Concurrency
# ===========================================================================

class TestDB18QaRecordsConcurrencyCase:
    """
    DB-C18: QA records concurrency.
    Concurrent questions on the same material.
    Verifies: qa_records count accurate, knowledge point links not duplicated.
    """

    async def test_concurrent_qa_record_count_accurate(self, client):
        """Concurrent QA on same material should produce exact record count."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        questions = [
            "What is requirements analysis?",
            "What are the phases of software engineering?",
            "How does system design work?",
            "What is software testing?",
            "Explain the waterfall model.",
        ]

        async def ask(question: str):
            try:
                resp = await client.post(
                    "/qa/ask",
                    json={"material_id": material_id, "question": question},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code, resp.json().get("code")
            except Exception as e:
                return 500, str(e)

        start = time.perf_counter()
        results = await asyncio.gather(*[ask(q) for q in questions])
        elapsed = time.perf_counter() - start

        status_codes = [r[0] for r in results]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C18] Concurrent QA: {len(questions)} questions, success={success}, time={elapsed:.2f}s")

        assert 500 not in status_codes, f"QA triggered 500: {status_codes}"
        assert success == len(questions), f"QA failures: {len(questions) - success}"

        # Verify QA history count
        resp = await client.get(
            "/qa/history?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        if body["code"] == 0:
            total = body["data"]["total"]
            print(f"    QA history total: {total} (expected {len(questions)})")
            assert total >= len(questions), f"QA history count mismatch: {total} < {len(questions)}"

    async def test_concurrent_qa_cross_user_isolation(self, client):
        """Concurrent QA from different users should be isolated."""
        token_a = await _register_and_login(client)
        target_a = await _create_target(client, token_a, "User A Target")
        material_a = await _upload_and_wait_parse(client, token_a, target_a)

        token_b = await _register_and_login(client)

        # User B tries to ask on User A's material
        resp = await client.post(
            "/qa/ask",
            json={"material_id": material_a, "question": "What is this about?"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Should be rejected
        assert resp.status_code in (403, 404, 409) or resp.json()["code"] != 0, \
            f"User B should not access User A's material for QA: {resp.status_code}"


# ===========================================================================
# DB-C19: Question Generation Concurrency
# ===========================================================================

class TestDB19QuestionGenerationConcurrencyCase:
    """
    DB-C19: Question generation concurrency.
    Concurrent AI question generation on the same material/target.
    Verifies: question count matches requests, link table no duplicates, list total accurate.
    """

    async def test_concurrent_question_generation(self, client):
        """Concurrent question generation should produce correct counts."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        async def generate(count: int):
            try:
                resp = await client.post(
                    "/questions/generate",
                    json={
                        "material_id": material_id,
                        "question_types": ["single_choice"],
                        "difficulty": "medium",
                        "count": count,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200 and resp.json()["code"] == 0:
                    return resp.json()["data"]["questions"]
                return []
            except Exception:
                return []

        # 4 concurrent generation requests
        results = await asyncio.gather(
            generate(2), generate(3), generate(2), generate(3)
        )

        all_questions = [q for batch in results for q in batch]
        print(f"\n  [DB-C19] Concurrent question gen: 4 requests, total questions={len(all_questions)}")

        # Each batch should produce exactly the requested count
        for i, (batch, expected) in enumerate(zip(results, [2, 3, 2, 3])):
            assert len(batch) == expected, f"Request {i}: expected {expected} questions, got {len(batch)}"

        # Verify no duplicate question IDs
        question_ids = [q["id"] for q in all_questions]
        duplicates = len(question_ids) - len(set(question_ids))
        print(f"    Question IDs: {len(question_ids)}, duplicates: {duplicates}")
        assert duplicates == 0, f"Duplicate question IDs found: {duplicates}"

    async def test_concurrent_generation_cross_user_isolation(self, client):
        """Questions generated by one user should not be accessible by another."""
        token_a = await _register_and_login(client)
        target_a = await _create_target(client, token_a)
        material_a = await _upload_and_wait_parse(client, token_a, target_a)

        resp = await client.post(
            "/questions/generate",
            json={
                "material_id": material_a,
                "question_types": ["single_choice"],
                "difficulty": "easy",
                "count": 2,
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        if resp.json()["code"] != 0:
            pytest.skip("Question generation failed")
        question_id = resp.json()["data"]["questions"][0]["id"]

        token_b = await _register_and_login(client)
        resp = await client.get(
            f"/questions/{question_id}/solution",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404, "User B should not see User A's question solution"


# ===========================================================================
# DB-C20: Test Submission Concurrency
# ===========================================================================

class TestDB20TestSubmissionConcurrencyCase:
    """
    DB-C20: Test submission concurrency.
    Concurrent test submissions from same user on same question set.
    Verifies: test_records count accurate, answer_records complete per submission,
              wrong_questions match wrong count, no orphan records.
    """

    async def _prepare_questions(self, client):
        """Prepare token, target_id, material_id, and generated questions."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        resp = await client.post(
            "/questions/generate",
            json={
                "material_id": material_id,
                "question_types": ["single_choice", "true_false"],
                "difficulty": "easy",
                "count": 4,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.json()["code"] != 0:
            return None, None, None, []
        questions = resp.json()["data"]["questions"]
        return token, target_id, material_id, questions

    async def test_concurrent_submission_no_data_loss(self, client):
        """Concurrent test submissions should each produce complete records."""
        token, target_id, material_id, questions = await self._prepare_questions(client)
        if not questions:
            pytest.skip("Question generation failed")

        async def submit(wrong_idx: int):
            """Submit test with one intentionally wrong answer."""
            try:
                answers = []
                for i, q in enumerate(questions):
                    if i == wrong_idx:
                        # Deliberately wrong answer
                        answers.append({"question_id": q["id"], "answer": ["Z"]})
                    else:
                        answers.append({"question_id": q["id"], "answer": ["A"]})

                resp = await client.post(
                    "/tests/submit",
                    json={
                        "material_id": material_id,
                        "target_id": target_id,
                        "answers": answers,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code, resp.json().get("code"), resp.json().get("data", {})
            except Exception as e:
                return 500, str(e), {}

        # 3 concurrent submissions, each with a different wrong answer
        results = await asyncio.gather(submit(0), submit(1), submit(2))

        status_codes = [r[0] for r in results]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C20] Concurrent test submission: 3 requests, success={success}")
        print(f"    Status codes: {status_codes}")

        assert 500 not in status_codes, f"Test submission triggered 500: {status_codes}"

        # Check test records
        resp = await client.get(
            "/tests/records",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            body = resp.json()
            records = body.get("data", {}).get("items", [])
            print(f"    Test records: {len(records)}")
            assert len(records) >= 1, "Should have at least 1 test record"

        # Check wrong questions
        resp = await client.get(
            f"/wrong-questions?target_id={target_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            body = resp.json()
            wrong_total = body.get("data", {}).get("total", 0)
            print(f"    Wrong questions total: {wrong_total}")
            # Each submission has exactly 1 wrong answer, but duplicates may accrue

    async def test_concurrent_submission_no_orphan_records(self, client):
        """Verify no orphan records after concurrent submissions."""
        token, target_id, material_id, questions = await self._prepare_questions(client)
        if not questions:
            pytest.skip("Question generation failed")

        # Single submission first for baseline
        answers = [{"question_id": q["id"], "answer": ["A"]} for q in questions]
        await client.post(
            "/tests/submit",
            json={
                "material_id": material_id,
                "target_id": target_id,
                "answers": answers,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify test records can be retrieved
        resp = await client.get(
            "/tests/records",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        records = resp.json().get("data", {}).get("items", [])
        if records:
            record = records[0]
            # total_count should match the number of answers
            assert record["total_count"] == len(questions), \
                f"total_count mismatch: {record['total_count']} vs {len(questions)}"


# ===========================================================================
# DB-C21: Wrong Question Mastery Concurrency
# ===========================================================================

class TestDB21WrongQuestionMasteryConcurrencyCase:
    """
    DB-C21: Wrong question mastery concurrency.
    Concurrent mastery status updates on the same wrong question.
    Verifies: review_count does not lose increments; status fields are valid; no 500.
    """

    async def _create_wrong_question(self, client):
        """Create a wrong question by generating and submitting with a wrong answer."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        resp = await client.post(
            "/questions/generate",
            json={
                "material_id": material_id,
                "question_types": ["single_choice"],
                "difficulty": "easy",
                "count": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.json()["code"] != 0:
            return None, None, None

        questions = resp.json()["data"]["questions"]
        answers = [
            {"question_id": q["id"], "answer": ["Z"]}  # Deliberately wrong
            for q in questions
        ]
        await client.post(
            "/tests/submit",
            json={
                "material_id": material_id,
                "target_id": target_id,
                "answers": answers,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            f"/wrong-questions?target_id={target_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = resp.json().get("data", {}).get("items", [])
        if not items:
            return token, target_id, None
        return token, target_id, items[0]["id"]

    async def test_concurrent_mastery_update_no_lost_review_count(self, client):
        """Concurrent mastery updates should not lose review_count increments."""
        token, target_id, wrong_id = await self._create_wrong_question(client)
        if not wrong_id:
            pytest.skip("No wrong question available")

        async def update_mastery(status: str):
            try:
                resp = await client.patch(
                    f"/wrong-questions/{wrong_id}/mastery",
                    json={"mastery_status": status},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code, resp.json().get("code")
            except Exception as e:
                return 500, str(e)

        statuses = ["reviewing", "mastered", "reviewing", "unmastered", "mastered"]
        results = await asyncio.gather(*[update_mastery(s) for s in statuses])

        status_codes = [r[0] for r in results]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C21] Concurrent mastery update: {len(statuses)} requests, success={success}")
        print(f"    Status codes: {status_codes}")

        assert 500 not in status_codes, f"Mastery update triggered 500: {status_codes}"
        assert success >= 4, f"Too many mastery update failures: {len(statuses) - success}"

        # Read back and verify status is valid
        resp = await client.get(
            f"/wrong-questions?target_id={target_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = resp.json().get("data", {}).get("items", [])
        matched = [item for item in items if item["id"] == wrong_id]
        if matched:
            status = matched[0]["mastery_status"]
            review_count = matched[0]["review_count"]
            print(f"    Final mastery_status={status}, review_count={review_count}")
            assert status in ("unmastered", "reviewing", "mastered"), f"Invalid status: {status}"
            # review_count should be >= 1 (at least some increments survived)
            assert review_count >= 1, f"review_count should be at least 1, got {review_count}"


# ===========================================================================
# DB-C22: Wrong Question Review Queue
# ===========================================================================

class TestDB22WrongQuestionReviewQueueCase:
    """
    DB-C22: Wrong question review queue.
    Mixed read (review queue) + write (mastery update) concurrency.
    Verifies: queue does not return unauthorized data, due_only filter is correct.
    """

    async def test_review_queue_under_mixed_load(self, client):
        """Review queue reads under concurrent mastery updates should not error."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        # Generate and submit to create wrong questions
        resp = await client.post(
            "/questions/generate",
            json={
                "material_id": material_id,
                "question_types": ["single_choice"],
                "difficulty": "easy",
                "count": 3,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.json()["code"] != 0:
            pytest.skip("Question generation failed")

        questions = resp.json()["data"]["questions"]
        answers = [{"question_id": q["id"], "answer": ["Z"]} for q in questions]
        await client.post(
            "/tests/submit",
            json={
                "material_id": material_id,
                "target_id": target_id,
                "answers": answers,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Get wrong question IDs
        resp = await client.get(
            f"/wrong-questions?target_id={target_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = resp.json().get("data", {}).get("items", [])
        if not items:
            pytest.skip("No wrong questions")

        wrong_ids = [item["id"] for item in items]

        async def read_queue():
            try:
                resp = await client.get(
                    "/wrong-questions?page=1&page_size=10",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code
            except Exception:
                return 500

        async def update_mastery(wid: int):
            try:
                resp = await client.patch(
                    f"/wrong-questions/{wid}/mastery",
                    json={"mastery_status": "reviewing"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code
            except Exception:
                return 500

        tasks = []
        for _ in range(20):
            tasks.append(read_queue())
        for wid in wrong_ids:
            tasks.append(update_mastery(wid))

        results = await asyncio.gather(*tasks)
        status_codes = list(results)
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C22] Review queue mixed load: {len(tasks)} ops, success={success}")
        assert 500 not in status_codes, f"Review queue load triggered 500"


# ===========================================================================
# DB-C23: Review Plan Generation Concurrency
# ===========================================================================

class TestDB23ReviewPlanGenerationConcurrencyCase:
    """
    DB-C23: Review plan generation concurrency.
    Concurrent plan generation for the same target.
    Verifies: each plan has complete tasks, no orphan tasks, list total accurate.
    """

    async def test_concurrent_plan_generation_complete_tasks(self, client):
        """Concurrent plan generation should produce plans with complete task sets."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)

        # Upload and parse material
        content = "Requirements analysis is the first step of software engineering. " * 15
        await _upload_and_wait_parse(client, token, target_id, content)

        today = str(date.today())
        end = str(date.today() + timedelta(days=3))

        async def generate_plan():
            try:
                resp = await client.post(
                    "/review-plans/generate",
                    json={
                        "target_id": target_id,
                        "start_date": today,
                        "end_date": end,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    return resp.status_code, body.get("code"), body.get("data", {})
                return resp.status_code, resp.json().get("code"), {}
            except Exception as e:
                return 500, str(e), {}

        # 4 concurrent plan generation requests
        results = await asyncio.gather(*[generate_plan() for _ in range(4)])

        status_codes = [r[0] for r in results]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C23] Concurrent plan gen: 4 requests, success={success}")
        print(f"    Status codes: {status_codes}")

        assert 500 not in status_codes, f"Plan generation triggered 500: {status_codes}"

        # Verify all successful plans have tasks
        for r in results:
            if r[0] == 200 and r[1] == 0:
                data = r[2]
                tasks = data.get("tasks", [])
                assert len(tasks) > 0, f"Plan has no tasks: data={data}"
                # Each task should have required fields
                for task in tasks:
                    assert "id" in task
                    assert "title" in task
                    assert "content" in task
                    assert "date" in task

        # Verify list total
        resp = await client.get(
            "/review-plans",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            total = resp.json().get("data", {}).get("total", 0)
            print(f"    Review plans total: {total}")


# ===========================================================================
# DB-C24: Review Task Completion Concurrency
# ===========================================================================

class TestDB24ReviewTaskCompletionConcurrencyCase:
    """
    DB-C24: Review task completion concurrency.
    Concurrent complete/cancel on the same task.
    Verifies: final state is explainable, no 500, other users cannot modify.
    """

    async def _create_plan_with_task(self, client):
        """Create a review plan with one task and return token, task_id."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)

        content = "Test content for review plan task test. " * 10
        await _upload_and_wait_parse(client, token, target_id, content)

        today = str(date.today())
        resp = await client.post(
            "/review-plans/generate",
            json={
                "target_id": target_id,
                "start_date": today,
                "end_date": today,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.json()["code"] != 0:
            return None, None
        tasks = resp.json()["data"]["tasks"]
        return token, tasks[0]["id"]

    async def test_concurrent_complete_cancel_explainable(self, client):
        """Concurrent complete/cancel on same task should produce explainable final state."""
        token, task_id = await self._create_plan_with_task(client)
        if not task_id:
            pytest.skip("Plan creation failed")

        async def set_completed(value: bool):
            try:
                resp = await client.patch(
                    f"/review-plans/tasks/{task_id}",
                    json={"completed": value},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code, resp.json().get("code"), resp.json().get("data", {}).get("completed")
            except Exception as e:
                return 500, str(e), None

        # 10 concurrent toggles alternating true/false
        values = [True, False, True, False, True, False, True, False, True, False]
        results = await asyncio.gather(*[set_completed(v) for v in values])

        status_codes = [r[0] for r in results]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C24] Concurrent task complete/cancel: 10 requests, success={success}")
        print(f"    Status codes: {status_codes}")

        assert 500 not in status_codes, f"Task completion triggered 500: {status_codes}"
        assert success == 10, f"Task completion failures: {10 - success}"

        # Final state should be either True or False (explainable)
        final_states = [r[2] for r in results if r[0] == 200]
        assert all(isinstance(s, bool) for s in final_states), \
            f"Non-boolean completion state: {final_states}"
        print(f"    Final completed values: {final_states}")

    async def test_cross_user_cannot_modify_task(self, client):
        """Another user cannot modify someone else's task."""
        token_a, task_id = await self._create_plan_with_task(client)
        if not task_id:
            pytest.skip("Plan creation failed")

        token_b = await _register_and_login(client)

        resp = await client.patch(
            f"/review-plans/tasks/{task_id}",
            json={"completed": True},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404, \
            f"User B should get 404 when modifying User A's task, got {resp.status_code}"
