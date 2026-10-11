#!/usr/bin/env bash
# P12.6 prep — NOT the rehearsal itself (that's explicitly a human task,
# §13-build-b marks it "human": running the real 6-minute storyboard
# live, three times in a row, per §12.2's wow-moment list). What IS
# automatable: everything that should be green BEFORE a human spends
# their own time rehearsing. Run this first; only pick up the actual
# rehearsal once it's clean.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "=== 1/4: doctor (system + LLM/cloud preflight) ==="
just doctor
DOCTOR_STATUS=$?

echo
echo "=== 2/4: chaos drills ==="
(cd scripts/chaos && ./kill_worker.sh && ./kill_brain.sh && ./network_and_rate_limit.sh && ./disk_low.sh)
CHAOS_STATUS=$?

echo
echo "=== 3/4: acceptance suite (writes var/reports/acceptance.json) ==="
python3 scripts/run_acceptance_suite.py
ACCEPTANCE_STATUS=$?

echo
echo "=== 4/4: full test suites (cargo + pytest x3 + vitest) ==="
just test
TEST_STATUS=$?

echo
echo "================ SUMMARY ================"
echo "doctor:     $([ $DOCTOR_STATUS -eq 0 ] && echo OK || echo 'see above — some checks are informational, not blocking')"
echo "chaos:      $([ $CHAOS_STATUS -eq 0 ] && echo OK || echo FAILED)"
echo "acceptance: $([ $ACCEPTANCE_STATUS -eq 0 ] && echo 'OK (0 evidence-test failures)' || echo FAILED)"
echo "tests:      $([ $TEST_STATUS -eq 0 ] && echo OK || echo FAILED)"
echo
echo "Next (human, not automatable): run the real 6-minute storyboard"
echo "(docs/_parts/12-demo.md §12.1) live, three times in a row, checking"
echo "every §12.2 wow-moment actually lands each time. This script only"
echo "proves the system is ready for that — it doesn't replace it."

[ $CHAOS_STATUS -eq 0 ] && [ $ACCEPTANCE_STATUS -eq 0 ] && [ $TEST_STATUS -eq 0 ]
