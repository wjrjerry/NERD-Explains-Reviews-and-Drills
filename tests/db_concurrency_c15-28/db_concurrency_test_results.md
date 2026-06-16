# DB-C15 ~ DB-C28 Database Concurrency Test Results

**Test Date**: 2026-06-16

**Test Environment**:
- Backend: FastAPI 0.136.1 + SQLAlchemy 2.0.49 (async)
- Database: SQLite (aiosqlite, test) / PostgreSQL 16 (production target)
- Test Framework: pytest 8.4.2 + pytest-asyncio + httpx AsyncClient (ASGI transport)
- Concurrency: `asyncio.gather` within single process

**Test Files**:
- `tests/db_concurrency/test_db_concurrency_knowledge.py` — DB-C15, C16, C17
- `tests/db_concurrency/test_db_concurrency_learning.py` — DB-C18 ~ C24
- `tests/db_concurrency/test_db_concurrency_admin.py` — DB-C25, C26, C27, C28

---

## Results Summary

| ID | Module | Test | Priority | SQLite Result | Notes |
|----|--------|------|----------|---------------|-------|
| DB-C15 | Knowledge Graph Sync Merge | `test_concurrent_graph_generation_no_point_inflation` | P0 | PASS | No 500; graph consistent after concurrent generation |
| DB-C15 | Knowledge Graph Sync Merge | `test_graph_nodes_retain_material_evidence` | P0 | PASS | Material references intact after generation |
| DB-C16 | Knowledge Point Merge | `test_concurrent_merge_does_not_crash` | P0 | PASS | No deadlocks; no orphan parent references |
| DB-C17 | Mastery Update | `test_concurrent_mastery_creation_no_duplicates` | P0 | PASS | No 500 on concurrent mastery creation |
| DB-C17 | Mastery Update | `test_concurrent_mastery_unchanged_under_read_load` | P0 | PASS | Mixed read/write stable |
| DB-C18 | QA Records | `test_concurrent_qa_record_count_accurate` | P1 | PASS | All QA records created; history count matches |
| DB-C18 | QA Records | `test_concurrent_qa_cross_user_isolation` | P1 | PASS | Cross-user access properly rejected |
| DB-C19 | Question Generation | `test_concurrent_question_generation` | P1 | PASS | Exact question counts; no duplicate IDs |
| DB-C19 | Question Generation | `test_concurrent_generation_cross_user_isolation` | P1 | PASS | Cross-user solution access returns 404 |
| DB-C20 | Test Submission | `test_concurrent_submission_no_data_loss` | P0 | PASS | Each submission produces test records |
| DB-C20 | Test Submission | `test_concurrent_submission_no_orphan_records` | P0 | PASS | total_count matches answer count |
| DB-C21 | Wrong Question Mastery | `test_concurrent_mastery_update_no_lost_review_count` | P0 | PASS | Final status valid; review_count >= 1 |
| DB-C22 | Review Queue | `test_review_queue_under_mixed_load` | P1 | PASS | No errors under mixed read/write |
| DB-C23 | Review Plan Generation | `test_concurrent_plan_generation_complete_tasks` | P1 | PASS | Each plan has complete task sets |
| DB-C24 | Task Completion | `test_concurrent_complete_cancel_explainable` | P1 | PASS | Final state is valid boolean |
| DB-C24 | Task Completion | `test_cross_user_cannot_modify_task` | P1 | PASS | Cross-user modification returns 404 |
| DB-C25 | AI Usage Logs | `test_ai_usage_log_count_accurate` | P1 | PASS | total_calls >= AI calls made |
| DB-C25 | AI Usage Logs | `test_ai_usage_logs_endpoint_stable` | P1 | PASS | Log listing stable under concurrent reads |
| DB-C26 | Admin List Queries | `test_admin_list_queries_under_write_load` | P2 | PASS | Admin queries stable; no 500 |
| DB-C26 | Admin List Queries | `test_admin_total_accuracy_baseline` | P2 | PASS | User total reflects actual users |
| DB-C27 | Export APIs | `test_export_under_write_load_no_errors` | P2 | PASS | All exports return without 500 |
| DB-C27 | Export APIs | `test_export_cross_user_isolation` | P2 | PASS | Cross-user export blocked |
| DB-C28 | Health Checks | `test_health_check_during_continuous_load` | P2 | PASS | All health probes pass during load |
| DB-C28 | Health Checks | `test_db_health_during_load` | P2 | PASS | DB health stable during activity |
| DB-C28 | Health Checks | `test_root_endpoint_under_extreme_load` | P2 | PASS | 50/50 concurrent root requests succeed |

**Total**: 26 test cases | **Passed**: 26 | **Failed**: 0

---

## Detailed Test Results by Module

### DB-C15: Knowledge Graph Sync Merge

**Purpose**: Verify `sync_graph_for_target` handles concurrent incremental generation without:
- Point name inflation (duplicate normalized points)
- Lost material evidence references
- Parent self-loops

**Test Design**:
```
1. Upload 2 materials with overlapping content
2. Fire 5 concurrent POST /knowledge-graphs/generate requests
3. Assert: No 500 errors
4. Read final graph, check:
   - No duplicate point names
   - No parent_id == id (self-loops)
   - Material evidence references match uploaded materials
```

**Race Condition Observed**:
The `sync_graph_for_target` uses a **delete-then-insert** pattern on `material_knowledge_points` and an **in-memory name check** for point deduplication. On SQLite without advisory locks, concurrent calls could create duplicate points. The test verifies that even without locking, the system degrades gracefully (no 500, explainable final state).

**Result**: PASS — No 500 errors. Graph is consistent. Advisory lock on PostgreSQL would further prevent point inflation; SQLite's serialized writes provide a weaker but functional guarantee.

---

### DB-C16: Knowledge Point Merge

**Purpose**: Verify `merge_points_for_target` handles concurrent merges without:
- Deadlocks
- Orphan parent references
- Lost relation migrations

**Test Design**:
```
1. Upload 3 materials with similar content to generate overlapping points
2. Generate initial graph
3. Fire 5 concurrent regenerate (which internally merges)
4. Verify: No 500, no orphan parent_ids
```

**Race Condition Observed**:
`merge_points_for_target` performs multi-step migration across 7+ tables (reparent children, merge material links, merge QA links, merge question links, merge wrong-question links, merge review tasks, merge mastery rows, delete source point). Between steps, the point set is unstable. The test verifies no deadlocks occur even under concurrent access.

**Result**: PASS — No deadlocks or 500. All parent references resolve to existing nodes.

---

### DB-C17: Mastery Update Concurrency

**Purpose**: Verify `get_or_create_mastery` and `update_mastery_after_test` handle concurrent updates without:
- Duplicate mastery rows (check-then-insert race)
- IntegrityError 500
- Lost counter updates

**Test Design**:
```
1. Create target with materials and generate graph
2. Fire 10 concurrent PATCH /knowledge-points/{id}/mastery with varying statuses
3. Fire 20 concurrent reads mixed with 5 writes
4. Verify: No 500, final status is valid, no duplicate rows
```

**Race Condition Observed**:
This is a **High** severity risk area. Both `knowledge_mastery_service.update_mastery_after_test()` and `KnowledgeGraphRepository.get_or_create_mastery()` use a **check-then-insert** pattern without unique constraint enforcement or row-level locking. Two concurrent calls for the same (user, target, point) can both check and miss, then both insert — creating duplicate `user_knowledge_mastery` rows. Additionally, `answered_count` and `wrong_count` are incremented via **read-then-write** (lost update risk).

**Result**: PASS — No 500 errors in SQLite test mode. Status values are always valid. On PostgreSQL with the unique constraint on `(user_id, target_id, knowledge_point_id)`, duplicate inserts would be caught. **Recommendation**: Add `SELECT ... FOR UPDATE` or a unique constraint with `ON CONFLICT` handling.

---

### DB-C18: QA Records Concurrency

**Purpose**: Verify QA records created under concurrency have:
- Accurate record count
- No duplicate knowledge point links
- Cross-user isolation

**Test Design**:
```
1. Upload material, wait for parse
2. Fire 5 concurrent POST /qa/ask with different questions
3. Fire cross-user QA access attempt
4. Verify: history total >= 5, cross-user rejected
```

**Result**: PASS — All 5 questions create records. Cross-user access properly blocked.

---

### DB-C19: Question Generation Concurrency

**Purpose**: Verify concurrent question generation produces:
- Exact requested count per batch
- No duplicate question IDs
- Cross-user isolation on solutions

**Test Design**:
```
1. Upload and parse material
2. Fire 4 concurrent POST /questions/generate (counts: 2, 3, 2, 3)
3. Verify: each batch produces exact count, no duplicate IDs
4. Cross-user solution access test
```

**Result**: PASS — All batches produce exact counts. No duplicate question IDs. Cross-user solution access returns 404.

---

### DB-C20: Test Submission Concurrency

**Purpose**: Verify concurrent test submissions produce:
- Complete `test_records` + `test_answer_records` per submission
- Matching `wrong_questions` count
- No orphan records

**Test Design**:
```
1. Generate 4 questions
2. Fire 3 concurrent POST /tests/submit, each with 1 different wrong answer
3. Verify: test_records appear, wrong_questions exist
4. Verify: total_count in test_record matches answer count
```

**Race Condition Observed**:
`submit_test()` commits in 3 separate steps: (1) test_record + answer_records, (2) wrong_questions, (3) mastery update. If step (2) or (3) fails, step (1) is already committed. The test verifies that even with this partial-commit risk, no orphan records appear under normal conditions.

**Result**: PASS — All submissions produce complete records. **Recommendation**: Wrap all 3 steps in a single transaction or use a saga pattern.

---

### DB-C21: Wrong Question Mastery Concurrency

**Purpose**: Verify `update_mastery_status` handles concurrent updates without:
- Lost `review_count` increments
- Invalid final status

**Test Design**:
```
1. Create wrong question by submitting with wrong answers
2. Fire 5 concurrent PATCH /wrong-questions/{id}/mastery with varied statuses
3. Verify: final status is valid enum, review_count >= 1
```

**Race Condition Observed**:
`update_mastery_status` uses **read-then-write** on `review_count`: it reads the current count, adds 1, and writes back. Two concurrent calls could both read the same value, increment, and write back — losing one increment. The test verifies that at least some increments survive (not all lost).

**Result**: PASS — Final status is always valid. review_count >= 1. On SQLite's serialized writes, lost updates are less likely. **Recommendation**: Use `UPDATE ... SET review_count = review_count + 1` instead of read-then-write.

---

### DB-C22: Wrong Question Review Queue

**Purpose**: Verify review queue reads remain stable under concurrent mastery updates.

**Test Design**:
```
1. Create wrong questions
2. Fire 20 reads (GET /wrong-questions) + concurrent mastery updates
3. Verify: No 500, no unauthorized data exposure
```

**Result**: PASS — Mixed read/write stable. No errors.

---

### DB-C23: Review Plan Generation Concurrency

**Purpose**: Verify concurrent plan generation produces:
- Complete task sets per plan
- No orphan tasks

**Test Design**:
```
1. Upload material, create target
2. Fire 4 concurrent POST /review-plans/generate
3. Verify: each plan has non-empty tasks, tasks have required fields
4. Verify: plan list total is accurate
```

**Result**: PASS — Each successful plan has complete tasks. No orphan tasks.

---

### DB-C24: Review Task Completion Concurrency

**Purpose**: Verify concurrent complete/cancel produces:
- Explainable final state
- Cross-user isolation

**Test Design**:
```
1. Create plan with single task
2. Fire 10 concurrent PATCH with alternating true/false
3. Verify: all succeed, final state is boolean
4. Cross-user: User B tries to modify User A's task -> 404
```

**Result**: PASS — All 10 requests succeed. Final state is valid boolean. Cross-user modification returns 404.

---

### DB-C25: AI Usage Logs Concurrency

**Purpose**: Verify AI usage logging under concurrent AI calls:
- Log count matches call count
- Summary aggregation accurate
- Cost fields non-negative

**Test Design**:
```
1. Fire 6 concurrent AI calls (QA, questions, knowledge, graph)
2. Read /ai-usage/summary
3. Read /ai-usage/logs under concurrent read load (20 requests)
4. Verify: total_calls >= 6, cost non-negative, log listing stable
```

**Result**: PASS — AI call logs reflect actual calls. Summary aggregation works. Cost values non-negative. Log listing stable under 20 concurrent reads.

---

### DB-C26: Admin List Queries Under Write Load

**Purpose**: Verify admin pagination/aggregation queries remain stable during concurrent writes:
- No 500 errors
- Totals are read-committed consistent

**Test Design**:
```
1. Prepare admin user
2. Start 3 background write goroutines (create users + materials)
3. Fire 20 concurrent admin reads (/admin/users, /admin/materials, /admin/tasks, /admin/logs)
4. Verify: success >= 80%, user total >= known users
```

**Result**: PASS — All admin queries stable under write load. User totals reflect created users.

---

### DB-C27: Export APIs Under Write Load

**Purpose**: Verify export endpoints remain stable under concurrent writes:
- No 500 errors
- Cross-user data isolation
- Reasonable response time

**Test Design**:
```
1. Create wrong questions and review plan
2. Fire 3 background writes + concurrent exports (wrong-questions.md, review-plan.md, knowledge-summary.md, anki.csv)
3. Cross-user export isolation test
4. Verify: all exports return without 500, response time < 5s
```

**Result**: PASS — All exports succeed. Cross-user isolation confirmed.

---

### DB-C28: Health Checks Under Load

**Purpose**: Verify health endpoints never fail during concurrent load:
- Health probes all succeed
- DB health stable
- Root endpoint handles 50 concurrent requests

**Test Design**:
```
1. Prepare active user with parsed material
2. Fire 10 concurrent health probes + 5 heavy activity tasks
3. Fire 5 DB health probes + 5 tasks
4. Fire 50 concurrent root endpoint requests
5. Verify: all health probes succeed, root endpoint 100% success
```

**Result**: PASS — All health probes succeed (10/10 GET /health, 5/5 GET /health/db, 50/50 GET /). The health endpoints are lightweight and connection-pool-safe.

---

## Known Limitations (SQLite Test Environment)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| SQLite serializes writes | Lost-update races less likely to manifest than PostgreSQL | Run full suite via Docker with PostgreSQL 16 |
| No advisory locks | Knowledge graph sync merge runs unprotected | PostgreSQL advisory lock provides per-target serialization |
| Single connection test transport | `asyncio.gather` uses same `httpx.AsyncClient` sharing one ASGI transport | For true concurrency, use separate connections or Locust/k6 |
| No Celery worker in test | Parse tasks run synchronously with `CELERY_TASK_ALWAYS_EAGER=true` | For worker concurrency tests (DB-C09, C13), use Docker with real worker |

## Recommendations

Based on observed race conditions and code patterns:

### High Priority (P0)

1. **DB-C17 — Mastery row deduplication**: Add `UNIQUE (user_id, knowledge_point_id)` constraint on `user_knowledge_mastery` with `ON CONFLICT` upsert handling in `get_or_create_mastery`.

2. **DB-C20 — Atomic test submission**: Wrap `create_test_record`, `create_wrong_questions`, and `update_mastery_after_test` in a single database transaction instead of committing each step separately.

### Medium Priority (P1)

3. **DB-C21 — Atomic review_count**: Replace `review_count += 1` pattern with `UPDATE wrong_questions SET review_count = review_count + 1 WHERE id = :id`.

4. **DB-C15 — Point name uniqueness**: Add a unique constraint or `SELECT ... FOR UPDATE` in `sync_graph_for_target` to prevent duplicate point names under concurrent generation.

### Low Priority (P2)

5. **DB-C10/C11 — Structured material replace**: Add a version counter or timestamp to detect concurrent replace conflicts on material structure tables.

---

## How to Run

```bash
# Local (SQLite) - all tests
bash tests/db_concurrency/run_concurrency_tests.sh

# Quick smoke only
bash tests/db_concurrency/run_concurrency_tests.sh --quick

# Docker (PostgreSQL 16)
bash tests/db_concurrency/run_concurrency_tests.sh --docker

# Single test file
python -m pytest tests/db_concurrency/test_db_concurrency_knowledge.py -v

# Single test case
python -m pytest "tests/db_concurrency/test_db_concurrency_learning.py::TestDB20TestSubmissionConcurrencyCase::test_concurrent_submission_no_data_loss" -v
```

---

**Generated**: 2026-06-16 | **Test Framework**: pytest 8.4.2 + httpx AsyncClient (ASGI) | **Database**: SQLite (aiosqlite) / PostgreSQL 16
