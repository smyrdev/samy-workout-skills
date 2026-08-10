#!/usr/bin/env bash
# Covers run_claude itself — the harness the two agent tests are built on.
#
# Offline and deterministic: CLAUDE_BIN points at a fake CLI, so none of this
# costs a token. That indirection exists for exactly this reason; without it
# the only way to exercise the failure paths is to wait for a real one.
#
# What is being pinned is the difference between "the agent answered something
# wrong" and "the agent never answered". Those must not look alike to a caller:
# a CLI that times out or errors used to leave $(run_claude ...) holding an
# empty string, and every content assertion downstream then failed with a
# message blaming the agent's reasoning.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

PROJECT=$(create_test_project)
trap 'cleanup_test_project "$PROJECT"' EXIT

# Three fake CLIs standing in for the three things a real one does.
cat > "$PROJECT/ok" <<'EOF'
#!/usr/bin/env bash
echo "FIXTURE-ANSWER: it writes to plans/"
exit 0
EOF
cat > "$PROJECT/slow" <<'EOF'
#!/usr/bin/env bash
echo "FIXTURE-PARTIAL: starting to answer"
sleep 30
EOF
cat > "$PROJECT/boom" <<'EOF'
#!/usr/bin/env bash
echo "FIXTURE-ERROR: not logged in" >&2
exit 1
EOF
# Ignores SIGTERM, like the real CLI does — a plain `timeout` reports a
# deadline it never enforces, and waits for this to exit on its own.
cat > "$PROJECT/stubborn" <<'EOF'
#!/usr/bin/env bash
trap "" TERM
echo "FIXTURE-STUBBORN: ignoring TERM"
sleep 60
EOF
chmod +x "$PROJECT/ok" "$PROJECT/slow" "$PROJECT/boom" "$PROJECT/stubborn"

echo "=== Agent Test Harness ==="
echo ""

echo "A successful run reaches the caller"
output=$(CLAUDE_BIN="$PROJECT/ok" run_claude "any prompt" 10 "Read")
rc=$?
assert_exit_code 0 "$rc" "run_claude passes the CLI's exit code through"
assert_contains "$output" "FIXTURE-ANSWER" "the answer is captured on stdout"
echo ""

echo "A timeout is reported as a timeout, not as a wrong answer"
output=$(CLAUDE_BIN="$PROJECT/slow" run_claude "any prompt" 2 "Read")
rc=$?
assert_exit_code 124 "$rc" "a timed-out run returns 124"
assert_contains "$output" "FIXTURE-PARTIAL" \
    "what the CLI did emit still reaches the caller instead of going to stderr"
out=$(assert_agent_responded "$rc" "$output" "the prompt" 2>&1)
assert_exit_code 1 "$?" "assert_agent_responded fails the run"
assert_contains "$out" "timed out" "and says the CLI timed out, naming no content"
echo ""

echo "A CLI error is reported as an error"
output=$(CLAUDE_BIN="$PROJECT/boom" run_claude "any prompt" 10 "Read")
rc=$?
assert_exit_code 1 "$rc" "a failing run passes its exit code through"
assert_contains "$output" "FIXTURE-ERROR" "the CLI's own diagnosis reaches the caller"
out=$(assert_agent_responded "$rc" "$output" "the prompt" 2>&1)
assert_exit_code 1 "$?" "assert_agent_responded fails the run"
assert_contains "$out" "exited 1" "and says how the CLI exited"
echo ""

# The timeout has to be a real bound, not a report. The CLI ignores SIGTERM,
# and a plain `timeout` then returns 124 on schedule while still blocking until
# the process exits by itself — which is how one agent test file consumed 3493
# seconds under a 900-second budget.
echo "The timeout is enforced, not just reported"
start=$(date +%s)
output=$(CLAUDE_BIN="$PROJECT/stubborn" run_claude "any prompt" 3 "Read")
rc=$?
elapsed=$(( $(date +%s) - start ))
if [ "$elapsed" -lt 20 ]; then
    _pass "a CLI that ignores SIGTERM is killed near the deadline (${elapsed}s)"
else
    _fail "a CLI that ignores SIGTERM is killed near the deadline"
    echo "    budget was 3s, run took ${elapsed}s — the deadline was reported, not enforced"
fi
out=$(assert_agent_responded "$rc" "$output" "the prompt" 2>&1)
assert_exit_code 1 "$?" "assert_agent_responded fails a killed run"
assert_contains "$out" "timed out" "a killed run reads as a timeout, not as a mystery exit code"
echo ""

echo "A good run is waved through"
output=$(CLAUDE_BIN="$PROJECT/ok" run_claude "any prompt" 10 "Read")
rc=$?
if assert_agent_responded "$rc" "$output" "the prompt" > /dev/null 2>&1; then
    _pass "assert_agent_responded passes a run that answered"
else
    _fail "assert_agent_responded passes a run that answered"
fi

finish_tests
