#!/usr/bin/env bash
# The runner's own gates — the ones that keep a green run honest. A suite that
# tests run_claude rigorously but never its runner would miss the cheapest
# failure of all: run-skill-tests.sh reporting PASSED after executing nothing.
#
# Every invocation below errors out before any test file executes, or runs a
# copy of the runner somewhere it can find no test files — so none of this
# recurses into the suite it is part of.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

RUNNER="$SCRIPT_DIR/run-skill-tests.sh"

# Run the runner, capturing stdout+stderr in $out and the exit code in $code.
run_runner() {
    out=$(bash "$RUNNER" "$@" 2>&1)
    code=$?
}

echo "=== Test Runner Gates ==="
echo ""

echo "A typo never becomes a green run"
run_runner --test no-such-test.sh
assert_exit_code 1 "$code" "an unknown --test name is an error, not a skip"
assert_contains "$out" "unknown test" "says the name is unknown"
echo ""

echo "A missing listed file fails the run"
# A copy of the runner in an empty directory finds none of its listed test
# files — the state a bad rename leaves behind. Zero tests executed must be a
# failure, not a summary that says PASSED over three zeros.
STAGE=$(create_test_project)
trap 'cleanup_test_project "$STAGE"' EXIT
cp "$RUNNER" "$STAGE/run-skill-tests.sh"
out=$(bash "$STAGE/run-skill-tests.sh" 2>&1)
code=$?
assert_exit_code 1 "$code" "a run that skipped every file reports failure"
assert_contains "$out" "STATUS: FAILED" "the summary says FAILED"
assert_contains "$out" "Passed:  0" "and it ran nothing"
echo ""

echo "--test does not bypass the integration gate"
run_runner --test test-onboarding-agent.sh
assert_exit_code 1 "$code" "an integration test without -i is refused"
assert_contains "$out" "add --integration" "points at the flag to use"

finish_tests
