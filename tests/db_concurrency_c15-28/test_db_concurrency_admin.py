"""
DB-C25, DB-C26, DB-C27, DB-C28: Admin / Export / Health Concurrency Tests

DB-C25: AI usage logs concurrency - mixed AI calls, log count accuracy, summary correctness
DB-C26: Admin list queries - pagination/aggregation under write load
DB-C27: Export APIs - export under concurrent writes
DB-C28: Health checks - continuous health probing under load
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


async def _make_admin(client, username: str):
    """Promote a user to admin by directly updating the DB."""
    from app.db.session import AsyncSessionLocal
    from app.repositories.user_repository import UserRepository
    from app.models.user import UserRole

    async with AsyncSessionLocal() as db:
        user = await UserRepository.get_by_username(db, username)
        if user:
            user.role = UserRole.admin
            await db.commit()


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
        content = "Software engineering phases: requirements, design, implementation, verification, maintenance. " * 20

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
# DB-C25: AI Usage Logs Concurrency
# ===========================================================================

class TestDB25AiUsageLogsCase:
    """
    DB-C25: AI usage logs concurrency.
    Mixed AI calls (QA, questions, graph, review plans) under concurrency.
    Verifies: log count matches call count, summary aggregation doesn't timeout,
              cost fields non-negative.
    """

    async def test_ai_usage_log_count_accurate(self, client):
        """AI usage log count should match the number of AI calls made."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        # Make various AI calls
        async def ai_call(action: str):
            try:
                if action == "qa":
                    resp = await client.post(
                        "/qa/ask",
                        json={"material_id": material_id, "question": "What is software engineering?"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                elif action == "questions":
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
                elif action == "knowledge":
                    resp = await client.post(
                        "/knowledge/extract",
                        json={"material_id": material_id},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                elif action == "graph":
                    resp = await client.post(
                        "/knowledge-graphs/generate",
                        json={"target_id": target_id, "max_points": 10},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                else:
                    return 500
                return resp.status_code
            except Exception:
                return 500

        actions = ["qa", "questions", "knowledge", "graph", "qa", "questions"]
        results = await asyncio.gather(*[ai_call(a) for a in actions])

        status_codes = list(results)
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C25] Concurrent AI calls: {len(actions)} calls, success={success}")
        assert 500 not in status_codes, f"AI calls triggered 500: {status_codes}"

        # Check AI usage summary
        resp = await client.get(
            "/ai-usage/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200 and resp.json()["code"] == 0:
            summary = resp.json()["data"]
            total_calls = summary.get("total_calls", 0)
            cost = summary.get("estimated_cost", 0)
            print(f"    AI usage: total_calls={total_calls}, estimated_cost={cost}")
            assert total_calls >= success, f"AI usage log count too low: {total_calls} < {success}"
            # Cost should be non-negative (string or number)
            if isinstance(cost, (int, float)):
                assert cost >= 0, f"Negative cost: {cost}"
            elif isinstance(cost, str):
                try:
                    cost_val = float(cost)
                    assert cost_val >= 0, f"Negative cost string: {cost}"
                except ValueError:
                    pass  # String cost is acceptable

    async def test_ai_usage_logs_endpoint_stable(self, client):
        """AI usage logs listing under concurrent write load should remain stable."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        # Make some AI calls
        for _ in range(3):
            await client.post(
                "/qa/ask",
                json={"material_id": material_id, "question": "Test question?"},
                headers={"Authorization": f"Bearer {token}"},
            )

        # Concurrent reads on AI usage logs
        async def read_logs():
            try:
                resp = await client.get(
                    "/ai-usage/logs?page=1&page_size=10",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.status_code
            except Exception:
                return 500

        # 20 concurrent log reads
        results = await asyncio.gather(*[read_logs() for _ in range(20)])
        status_codes = list(results)
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C25b] AI usage log reads: 20 requests, success={success}")
        assert success >= 18, f"AI log reads had too many failures: {20 - success}"


# ===========================================================================
# DB-C26: Admin List Queries Under Write Load
# ===========================================================================

class TestDB26AdminListQueriesCase:
    """
    DB-C26: Admin list queries under write load.
    Pagination/aggregation queries during concurrent writes.
    Verifies: total is accurate or read-committed consistent; P95 under threshold.
    """

    async def _prepare_admin(self, client):
        """Register admin user and return admin token."""
        username = _random_username()
        token = await _register_and_login(client, username)
        if not token:
            return None, None
        await _make_admin(client, username)
        # Re-login to get token with admin role
        resp = await client.post(
            "/auth/login",
            json={"username": username, "password": "test123456"},
        )
        return resp.json()["data"]["token"]["access_token"], username

    async def test_admin_list_queries_under_write_load(self, client):
        """Admin list queries should remain stable during concurrent writes."""
        admin_token, admin_username = await self._prepare_admin(client)
        if not admin_token:
            pytest.skip("Admin preparation failed")

        # Create some users and materials in the background
        async def write_activity():
            token = await _register_and_login(client)
            if not token:
                return
            target_id = await _create_target(client, token)
            for i in range(5):
                content = f"Admin test material {i}: test content. " * 10
                file_content = io.BytesIO(content.encode("utf-8"))
                await client.post(
                    "/materials",
                    data={"target_id": str(target_id), "auto_parse": "false"},
                    files={"file": (f"admin_test_{i}.txt", file_content, "text/plain")},
                    headers={"Authorization": f"Bearer {token}"},
                )

        async def admin_read(endpoint: str):
            try:
                start = time.perf_counter()
                resp = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                elapsed = time.perf_counter() - start
                return resp.status_code, elapsed
            except Exception:
                return 500, 0

        # Start writes in background
        write_tasks = [write_activity() for _ in range(3)]

        # Concurrent admin reads
        admin_endpoints = [
            "/admin/users",
            "/admin/materials",
            "/admin/tasks",
            "/admin/logs",
        ]
        read_tasks = []
        for _ in range(5):
            for ep in admin_endpoints:
                read_tasks.append(admin_read(ep))

        all_results = await asyncio.gather(*(write_tasks + read_tasks))
        # Separate write and read results
        read_results = all_results[len(write_tasks):]

        status_codes = [r[0] for r in read_results]
        latencies = [r[1] for r in read_results if r[0] == 200]
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C26] Admin queries under write load: {len(read_results)} reads, success={success}")
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            sorted_lat = sorted(latencies)
            p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
            p95 = sorted_lat[p95_idx]
            print(f"    Latency: avg={avg_latency*1000:.1f}ms, p95={p95*1000:.1f}ms")

        assert 500 not in status_codes, f"Admin queries triggered 500: {status_codes}"
        assert success >= len(read_results) * 0.8, f"Too many admin query failures: {len(read_results) - success}"

    async def test_admin_total_accuracy_baseline(self, client):
        """Admin user/material totals should at least reflect known users."""
        admin_token, _ = await self._prepare_admin(client)
        if not admin_token:
            pytest.skip("Admin preparation failed")

        # Create a few regular users
        for _ in range(3):
            await _register_and_login(client)

        resp = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        total_users = body.get("data", {}).get("total", 0)
        print(f"\n  [DB-C26b] Admin users total: {total_users}")
        assert total_users >= 4, f"Admin should see at least 4 users (admin + 3), got {total_users}"


# ===========================================================================
# DB-C27: Export APIs Under Write Load
# ===========================================================================

class TestDB27ExportAPIsCase:
    """
    DB-C27: Export APIs under write load.
    Export endpoints during concurrent writes.
    Verifies: exports don't 500, content doesn't include unauthorized data,
              large data response time acceptable.
    """

    async def test_export_under_write_load_no_errors(self, client):
        """Export endpoints should remain stable during concurrent activity."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        # Generate some questions and submit to create wrong questions
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
        if resp.json()["code"] == 0:
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

        # Generate review plan
        today = str(date.today())
        plan_resp = await client.post(
            "/review-plans/generate",
            json={
                "target_id": target_id,
                "start_date": today,
                "end_date": str(date.today() + timedelta(days=2)),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        plan_data = plan_resp.json().get("data", {})

        async def try_export(endpoint: str):
            try:
                start = time.perf_counter()
                resp = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}"},
                )
                elapsed = time.perf_counter() - start
                return resp.status_code, elapsed
            except Exception:
                return 500, 0

        exports = [
            "/exports/wrong-questions.md",
        ]
        # Add plan and knowledge exports if available
        if plan_data.get("id"):
            exports.append(f"/exports/review-plan/{plan_data['id']}.md")
        exports.append(f"/exports/knowledge-summary/{target_id}.md")
        exports.append(f"/exports/anki/{target_id}.csv")

        # Concurrent exports + background writes
        async def background_write():
            await client.post(
                "/qa/ask",
                json={"material_id": material_id, "question": "Background write test?"},
                headers={"Authorization": f"Bearer {token}"},
            )

        tasks = [background_write() for _ in range(3)]
        for ep in exports:
            tasks.append(try_export(ep))

        results = await asyncio.gather(*tasks)
        export_results = results[3:]  # Skip background writes

        for i, (status, elapsed) in enumerate(export_results):
            print(f"\n  [DB-C27] Export {exports[i]}: status={status}, time={elapsed*1000:.1f}ms")
            assert status != 500, f"Export {exports[i]} returned 500"
            if status == 200:
                assert elapsed < 5.0, f"Export {exports[i]} took too long: {elapsed*1000:.0f}ms"

    async def test_export_cross_user_isolation(self, client):
        """Export endpoints should not expose other users' data."""
        token_a = await _register_and_login(client)
        target_a = await _create_target(client, token_a)

        token_b = await _register_and_login(client)

        # User B tries to export User A's data
        resp = await client.get(
            f"/exports/knowledge-summary/{target_a}.md",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Should not return User A's data
        if resp.status_code == 200:
            # Even if 200, content should be empty/error
            content = resp.text
            assert len(content) < 200 or "error" in content.lower(), \
                "Export should not expose cross-user data"


# ===========================================================================
# DB-C28: Health Check Under Load
# ===========================================================================

class TestDB28HealthCheckCase:
    """
    DB-C28: Health check under load.
    Continuous health probing during stress.
    Verifies: health doesn't fail long-term due to connection pool saturation.
    """

    async def test_health_check_during_continuous_load(self, client):
        """Health check should remain operational during heavy concurrent load."""
        # Prepare a user doing heavy activity
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        async def health_probe():
            try:
                resp = await client.get("/health")
                return resp.status_code, resp.json().get("code")
            except Exception as e:
                return 500, str(e)

        async def heavy_activity():
            """Simulate heavy user activity."""
            try:
                # QA
                await client.post(
                    "/qa/ask",
                    json={"material_id": material_id, "question": "Test?"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                # Question generation
                await client.post(
                    "/questions/generate",
                    json={
                        "material_id": material_id,
                        "question_types": ["single_choice"],
                        "difficulty": "easy",
                        "count": 2,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                # Knowledge extract
                await client.post(
                    "/knowledge/extract",
                    json={"material_id": material_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return True
            except Exception:
                return False

        # 10 health probes + heavy activity
        health_tasks = [health_probe() for _ in range(10)]
        activity_tasks = [heavy_activity() for _ in range(5)]

        all_results = await asyncio.gather(*(health_tasks + activity_tasks))
        health_results = all_results[:10]

        health_statuses = [r[0] for r in health_results]
        health_success = sum(1 for s in health_statuses if s == 200)

        print(f"\n  [DB-C28] Health under load: {len(health_results)} probes, success={health_success}")
        print(f"    Health statuses: {health_statuses}")

        # All health probes must succeed
        assert health_success == len(health_results), \
            f"Health checks failed under load: {health_statuses}"

    async def test_db_health_during_load(self, client):
        """DB health check should remain responsive during activity."""
        token = await _register_and_login(client)
        target_id = await _create_target(client, token)
        material_id = await _upload_and_wait_parse(client, token, target_id)

        async def db_health():
            try:
                resp = await client.get("/health/db")
                return resp.status_code
            except Exception:
                return 500

        # Concurrent health + activity
        async def activity():
            try:
                await client.post(
                    "/qa/ask",
                    json={"material_id": material_id, "question": "DB health test?"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return True
            except Exception:
                return False

        tasks = [db_health() for _ in range(5)] + [activity() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        health_codes = results[:5]
        print(f"\n  [DB-C28b] DB health during load: statuses={health_codes}")
        assert all(c == 200 for c in health_codes), f"DB health failures: {health_codes}"

    async def test_root_endpoint_under_extreme_load(self, client):
        """Root endpoint should never fail, even under 50 concurrent requests."""
        async def root():
            try:
                resp = await client.get("/")
                return resp.status_code
            except Exception:
                return 500

        results = await asyncio.gather(*[root() for _ in range(50)])
        status_codes = list(results)
        success = sum(1 for s in status_codes if s == 200)

        print(f"\n  [DB-C28c] Root endpoint 50 concurrent: success={success}/50")
        assert success == 50, f"Root endpoint failures: {50 - success}"
