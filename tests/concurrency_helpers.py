from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def api_code(response: Any) -> int | None:
    try:
        return response.json().get("code")
    except Exception:
        return None


def api_ok(response: Any) -> bool:
    return getattr(response, "status_code", 0) == 200 and api_code(response) == 0


def no_server_error(response: Any) -> bool:
    return getattr(response, "status_code", 500) < 500


async def register_user(
    client: Any,
    *,
    username: str | None = None,
    password: str = "password123",
    display_name: str | None = None,
) -> dict[str, Any]:
    username = username or unique_name("db_user")
    response = await client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
            "display_name": display_name or username,
        },
    )
    assert api_ok(response), response.text
    return response.json()["data"]["user"]


async def login_user(
    client: Any,
    *,
    username: str,
    password: str = "password123",
) -> tuple[str, dict[str, Any]]:
    response = await client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert api_ok(response), response.text
    body = response.json()["data"]
    return body["token"]["access_token"], body["user"]


async def create_logged_in_user(
    client: Any,
    *,
    prefix: str = "db_user",
    password: str = "password123",
) -> tuple[str, dict[str, Any], str]:
    username = unique_name(prefix)
    user = await register_user(client, username=username, password=password)
    token, logged_in_user = await login_user(
        client,
        username=username,
        password=password,
    )
    return token, logged_in_user or user, username


async def create_study_target(
    client: Any,
    *,
    headers: dict[str, str],
    title: str | None = None,
) -> dict[str, Any]:
    response = await client.post(
        "/study-targets",
        json={
            "title": title or unique_name("target"),
            "subject": "database concurrency",
            "target_type": "exam",
            "exam_date": "2026-07-01",
            "review_goal": "Verify database concurrency behavior.",
        },
        headers=headers,
    )
    assert api_ok(response), response.text
    return response.json()["data"]["target"]


async def upload_text_material(
    client: Any,
    *,
    headers: dict[str, str],
    target_id: int,
    filename: str | None = None,
    auto_parse: bool = False,
    text: str | None = None,
) -> dict[str, Any]:
    filename = filename or f"{unique_name('material')}.txt"
    content = (
        text
        or "# Chapter 1\nDatabase transactions, locks, indexes, and isolation levels.\n"
        "Concurrency tests verify read-write races and state transitions.\n"
    )
    response = await client.post(
        "/materials",
        data={"target_id": str(target_id), "auto_parse": str(auto_parse).lower()},
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        headers=headers,
    )
    assert api_ok(response), response.text
    return response.json()["data"]["material"]


@dataclass
class ConcurrencyReport:
    case_id: str
    module: str
    code_paths: list[str]
    concurrency: int
    max_in_flight: int
    success_count: int
    failure_count: int
    elapsed_seconds: float
    status_counts: dict[str, int]
    code_counts: dict[str, int]
    notes: str = ""

    def print(self) -> None:
        paths = ", ".join(self.code_paths)
        print(
            "\n"
            f"[DB-CONCURRENCY] case={self.case_id}\n"
            f"  module={self.module}\n"
            f"  code_paths={paths}\n"
            f"  total_requests={self.concurrency}\n"
            f"  max_in_flight={self.max_in_flight}\n"
            f"  success={self.success_count}\n"
            f"  failed={self.failure_count}\n"
            f"  elapsed_seconds={self.elapsed_seconds:.4f}\n"
            f"  status_counts={self.status_counts}\n"
            f"  api_code_counts={self.code_counts}\n"
            f"  notes={self.notes}"
        )


async def run_concurrently(
    *,
    case_id: str,
    module: str,
    code_paths: list[str],
    concurrency: int,
    operation: Callable[[int], Awaitable[Any]],
    is_success: Callable[[Any], bool] | None = None,
    notes: str = "",
    max_in_flight: int | None = None,
) -> tuple[ConcurrencyReport, list[Any]]:
    max_in_flight = max_in_flight or env_int("DB_MAX_IN_FLIGHT", min(concurrency, 15))
    max_in_flight = max(1, min(concurrency, max_in_flight))
    semaphore = asyncio.Semaphore(max_in_flight)

    async def run_one(index: int) -> Any:
        async with semaphore:
            return await operation(index)

    start = time.perf_counter()
    results = await asyncio.gather(
        *(run_one(index) for index in range(concurrency)),
        return_exceptions=True,
    )
    elapsed = time.perf_counter() - start

    status_counter: Counter[str] = Counter()
    code_counter: Counter[str] = Counter()
    success_count = 0
    predicate = is_success or (lambda result: not isinstance(result, Exception))

    for result in results:
        if isinstance(result, Exception):
            status_counter[type(result).__name__] += 1
            code_counter["exception"] += 1
            continue

        status_counter[str(getattr(result, "status_code", "ok"))] += 1
        code_counter[str(api_code(result))] += 1
        if predicate(result):
            success_count += 1

    report = ConcurrencyReport(
        case_id=case_id,
        module=module,
        code_paths=code_paths,
        concurrency=concurrency,
        max_in_flight=max_in_flight,
        success_count=success_count,
        failure_count=concurrency - success_count,
        elapsed_seconds=elapsed,
        status_counts=dict(status_counter),
        code_counts=dict(code_counter),
        notes=notes,
    )
    report.print()
    return report, results
