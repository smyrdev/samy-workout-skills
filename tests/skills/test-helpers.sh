#!/usr/bin/env bash
# Helper functions for skill tests.
#
# Two families of assertions, deliberately named apart so they never shadow
# each other:
#   assert_contains       — on captured OUTPUT text, case-insensitive regex
#   assert_file_contains  — on a FILE's content, literal and case-sensitive
#
# Every failing assertion bumps TESTS_FAILED. End a test file with finish_tests.

TESTS_FAILED=0

# Print the footer every test file ends with, and exit 0/1 accordingly.
# Usage: finish_tests
finish_tests() {
    echo ""
    if [ "$TESTS_FAILED" -gt 0 ]; then
        echo "STATUS: FAILED ($TESTS_FAILED failures)"
        exit 1
    fi
    echo "STATUS: PASSED"
    exit 0
}

_pass() {
    echo "  [PASS] $1"
    return 0
}

_fail() {
    echo "  [FAIL] $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    return 1
}

# Run Claude Code with a prompt and capture output
# Usage: run_claude "prompt text" [timeout_seconds] [allowed_tools]
# CLAUDE_BIN overrides the CLI, which is how test-agent-harness.sh exercises
# the failure paths without spending a token.
run_claude() {
    local prompt="$1"
    local timeout="${2:-60}"
    local allowed_tools="${3:-}"
    local output_file=$(mktemp)

    # Build command as an argv array so timeout wraps claude directly.
    local cmd=("${CLAUDE_BIN:-claude}" -p "$prompt")
    if [ -n "$allowed_tools" ]; then
        cmd+=(--allowed-tools="$allowed_tools")
    fi

    # Run Claude in headless mode with timeout.
    # -k is what makes the deadline real. The CLI does not die on SIGTERM, and
    # a plain `timeout` then returns 124 on schedule while still blocking until
    # the process exits on its own — a budget that reports but never enforces.
    timeout -k 10 "$timeout" "${cmd[@]}" > "$output_file" 2>&1
    local exit_code=$?
    # Always on stdout, whatever happened. Callers capture this in $(...), and
    # routing the failure case to stderr instead would hand them an empty
    # string — turning "the CLI died" into a content assertion that blames the
    # agent's answer. A partial answer and the CLI's own error text are both
    # worth more than nothing.
    cat "$output_file"
    rm -f "$output_file"
    return $exit_code
}

# Guard an agent prompt before asserting on what it said.
# A run that timed out or errored must be reported once, as itself — not as
# three content assertions failing for a reason that has nothing to do with
# the skill under test. Returns 0 when the run is worth asserting on.
# Usage: if assert_agent_responded "$rc" "$output" "prompt name"; then ... fi
assert_agent_responded() {
    local rc="$1"
    local output="$2"
    local test_name="${3:-the prompt}"

    if [ "$rc" -eq 0 ] && [ -n "$output" ]; then
        return 0
    fi

    # 124 is timeout's own deadline signal; 137 is the SIGKILL that -k sends
    # when the CLI ignored SIGTERM. Both mean the same thing to a reader.
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        _fail "$test_name: the agent CLI timed out"
    elif [ "$rc" -ne 0 ]; then
        _fail "$test_name: the agent CLI exited $rc"
    else
        _fail "$test_name: the agent CLI said nothing"
    fi
    if [ -n "$output" ]; then
        echo "$output" | sed 's/^/    /'
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Assertions on captured output
# ---------------------------------------------------------------------------

# Check if output contains a pattern
# Usage: assert_contains "output" "pattern" "test name"
# Matching is case-insensitive: patterns are prose keywords, and models
# freely capitalize skill terms ("Profile", "Program File").
assert_contains() {
    local output="$1"
    local pattern="$2"
    local test_name="${3:-test}"

    if echo "$output" | grep -qi "$pattern"; then
        _pass "$test_name"
    else
        _fail "$test_name"
        echo "  Expected to find: $pattern"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    fi
}

# Check if output does NOT contain a pattern
# Usage: assert_not_contains "output" "pattern" "test name"
assert_not_contains() {
    local output="$1"
    local pattern="$2"
    local test_name="${3:-test}"

    if echo "$output" | grep -qi "$pattern"; then
        _fail "$test_name"
        echo "  Did not expect to find: $pattern"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    else
        _pass "$test_name"
    fi
}

# Check if output matches a count
# Usage: assert_count "output" "pattern" expected_count "test name"
assert_count() {
    local output="$1"
    local pattern="$2"
    local expected="$3"
    local test_name="${4:-test}"

    local actual
    actual=$(echo "$output" | grep -ci "$pattern") || actual=0

    if [ "$actual" -eq "$expected" ]; then
        _pass "$test_name (found $actual instances)"
    else
        _fail "$test_name"
        echo "  Expected $expected instances of: $pattern"
        echo "  Found $actual instances"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    fi
}

# Check if pattern A appears before pattern B
# Usage: assert_order "output" "pattern_a" "pattern_b" "test name"
assert_order() {
    local output="$1"
    local pattern_a="$2"
    local pattern_b="$3"
    local test_name="${4:-test}"

    # Get line numbers where patterns appear
    local line_a=$(echo "$output" | grep -ni "$pattern_a" | head -1 | cut -d: -f1)
    local line_b=$(echo "$output" | grep -ni "$pattern_b" | head -1 | cut -d: -f1)

    if [ -z "$line_a" ]; then
        _fail "$test_name: pattern A not found: $pattern_a"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    fi

    if [ -z "$line_b" ]; then
        _fail "$test_name: pattern B not found: $pattern_b"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    fi

    if [ "$line_a" -lt "$line_b" ]; then
        _pass "$test_name (A at line $line_a, B at line $line_b)"
    else
        _fail "$test_name"
        echo "  Expected '$pattern_a' before '$pattern_b'"
        echo "  But found A at line $line_a, B at line $line_b"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Assertions on files
# ---------------------------------------------------------------------------

# Check that a file exists and contains a literal string
# Usage: assert_file_contains "$file" "literal text" "test name"
assert_file_contains() {
    local file="$1"
    local pattern="$2"
    local test_name="${3:-test}"

    if [ ! -f "$file" ]; then
        _fail "$test_name"
        echo "    File not found: $file"
        return 1
    fi

    if grep -Fq -- "$pattern" "$file"; then
        _pass "$test_name"
    else
        _fail "$test_name"
        echo "    Expected to find: $pattern"
        echo "    In file: $file"
        return 1
    fi
}

# Check that a file exists and does NOT contain a literal string.
# The existence check matters: a missing file must fail here rather than
# pass vacuously.
# Usage: assert_file_not_contains "$file" "literal text" "test name"
assert_file_not_contains() {
    local file="$1"
    local pattern="$2"
    local test_name="${3:-test}"

    if [ ! -f "$file" ]; then
        _fail "$test_name"
        echo "    File not found: $file"
        return 1
    fi

    if grep -Fq -- "$pattern" "$file"; then
        _fail "$test_name"
        echo "    Did not expect to find: $pattern"
        echo "    In file: $file"
        return 1
    else
        _pass "$test_name"
    fi
}

# Check that a file does NOT exist — a refused run must not leave partial output
# Usage: assert_file_absent "$file" "test name"
assert_file_absent() {
    local file="$1"
    local test_name="${2:-test}"

    if [ -e "$file" ]; then
        _fail "$test_name"
        echo "    Expected no file at: $file"
        return 1
    else
        _pass "$test_name"
    fi
}

# Compare an expected exit code against an actual one
# Usage: assert_exit_code expected actual "test name"
assert_exit_code() {
    local expected="$1"
    local actual="$2"
    local test_name="${3:-test}"

    if [ "$actual" -eq "$expected" ]; then
        _pass "$test_name (exit $actual)"
    else
        _fail "$test_name"
        echo "    Expected exit code: $expected"
        echo "    Actual exit code:   $actual"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Create a temporary test project directory
# Usage: test_project=$(create_test_project)
create_test_project() {
    local test_dir=$(mktemp -d)
    echo "$test_dir"
}

# Cleanup test project
# Usage: cleanup_test_project "$test_dir"
cleanup_test_project() {
    local test_dir="$1"
    if [ -d "$test_dir" ]; then
        rm -rf "$test_dir"
    fi
}

# Populate a test project with a profile and a program file that has no
# volume block yet — the state onboarding leaves behind before step 5.
# The profile is the shipped example, so the fixture and the schema sample
# can never drift apart.
# Usage: create_test_profile "$project_dir" "$repo_root"
create_test_profile() {
    local project_dir="$1"
    local repo_root="$2"

    mkdir -p "$project_dir/programs"
    cp "$repo_root/skills/onboarding/examples/profile.example.json" "$project_dir/profile.json"

    cat > "$project_dir/programs/program-2026-08-06.json" <<'EOF'
{
  "$schema_version": "1.0",
  "created_at": "2026-08-06T09:15:00Z",
  "program": {
    "name": "Summer Build",
    "emoji": "💪",
    "primary_goal": "hypertrophy",
    "days_per_week": 6,
    "session_minutes": "60-90",
    "split": "upper_lower",
    "deload": true
  }
}
EOF

    echo "$project_dir"
}

# Export functions for use in tests
export -f _pass
export -f _fail
export -f finish_tests
export -f run_claude
export -f assert_agent_responded
export -f assert_contains
export -f assert_not_contains
export -f assert_count
export -f assert_order
export -f assert_file_contains
export -f assert_file_not_contains
export -f assert_file_absent
export -f assert_exit_code
export -f create_test_project
export -f cleanup_test_project
export -f create_test_profile
