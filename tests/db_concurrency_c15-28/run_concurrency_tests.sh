#!/usr/bin/env bash
# ==============================================================================
# DB-C15 ~ DB-C28 Concurrency Test Runner
# ==============================================================================
# Usage:
#   bash tests/db_concurrency/run_concurrency_tests.sh          # Run all
#   bash tests/db_concurrency/run_concurrency_tests.sh --quick  # Quick smoke only
#   bash tests/db_concurrency/run_concurrency_tests.sh --docker # Docker/PostgreSQL
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

export CELERY_TASK_ALWAYS_EAGER=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

MODE="full"
USE_DOCKER=false

for arg in "$@"; do
    case $arg in
        --quick) MODE="quick" ;;
        --docker) USE_DOCKER=true ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

echo_section() { echo -e "\n${CYAN}==== $1 ====${NC}"; }
echo_pass()   { echo -e "${GREEN}[PASS]${NC} $1"; }
echo_fail()  { echo -e "${RED}[FAIL]${NC} $1"; }
echo_info()  { echo -e "${YELLOW}[INFO]${NC} $1"; }

PYTEST_CMD="python -m pytest"
PYTEST_DIR="tests/db_concurrency"
PYTEST_OPTS="-v --tb=short -p conftest --rootdir=tests"

if $USE_DOCKER; then
    echo_info "Docker mode: running via docker compose exec"
    PYTEST_CMD="docker compose exec -T api python -m pytest"
    PYTEST_DIR="/app/tests/db_concurrency"
    PYTEST_OPTS="-v --tb=short -p conftest --rootdir=/app/tests"
fi

# ---- DB-C15: Knowledge Graph Sync Merge ----
echo_section "DB-C15: Knowledge Graph Sync Merge"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_knowledge.py::TestDB15KnowledgeGraphSyncMergeCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C15 (some failures expected with SQLite)"

# ---- DB-C16: Knowledge Point Merge ----
echo_section "DB-C16: Knowledge Point Merge"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_knowledge.py::TestDB16KnowledgePointMergeCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C16"

# ---- DB-C17: Mastery Update ----
echo_section "DB-C17: Mastery Update"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_knowledge.py::TestDB17MasteryUpdateConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C17"

# ---- DB-C18: QA Records ----
echo_section "DB-C18: QA Records Concurrency"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB18QaRecordsConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C18"

# ---- DB-C19: Question Generation ----
echo_section "DB-C19: Question Generation Concurrency"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB19QuestionGenerationConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C19"

# ---- DB-C20: Test Submission ----
echo_section "DB-C20: Test Submission Concurrency"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB20TestSubmissionConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C20"

# ---- DB-C21: Wrong Question Mastery ----
echo_section "DB-C21: Wrong Question Mastery"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB21WrongQuestionMasteryConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C21"

# ---- DB-C22: Review Queue ----
echo_section "DB-C22: Review Queue Mixed Load"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB22WrongQuestionReviewQueueCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C22"

# ---- DB-C23: Review Plan Generation ----
echo_section "DB-C23: Review Plan Generation"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB23ReviewPlanGenerationConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C23"

# ---- DB-C24: Task Completion ----
echo_section "DB-C24: Task Completion Concurrency"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_learning.py::TestDB24ReviewTaskCompletionConcurrencyCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C24"

# ---- DB-C25: AI Usage Logs ----
echo_section "DB-C25: AI Usage Logs"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_admin.py::TestDB25AiUsageLogsCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C25"

# ---- DB-C26: Admin List Queries ----
echo_section "DB-C26: Admin List Queries"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_admin.py::TestDB26AdminListQueriesCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C26"

# ---- DB-C27: Export APIs ----
echo_section "DB-C27: Export APIs"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_admin.py::TestDB27ExportAPIsCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C27"

# ---- DB-C28: Health Checks ----
echo_section "DB-C28: Health Checks Under Load"
$PYTEST_CMD "$PYTEST_DIR/test_db_concurrency_admin.py::TestDB28HealthCheckCase" $PYTEST_OPTS 2>&1 || echo_fail "DB-C28"

# ---- Summary ----
echo_section "Summary"
echo_info "All DB-C15 through DB-C28 test suites completed."
echo_info "For PostgreSQL-level validation, re-run with: bash $0 --docker"
