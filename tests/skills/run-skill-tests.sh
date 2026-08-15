#!/usr/bin/env bash
# Test runner for the skills in this repository.
# Offline tests run by default; --integration adds the ones that drive a real agent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " Skills Test Suite"
echo "========================================"
echo ""
echo "Repository: $(cd ../.. && pwd)"
echo "Test time: $(date)"
echo "Python: $(python --version 2>&1 || echo 'not found')"
echo ""

# Parse command line arguments
VERBOSE=false
SPECIFIC_TEST=""
TIMEOUT=""       # empty means "pick a default once we know the mode"
RUN_INTEGRATION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --test|-t)
            SPECIFIC_TEST="${2:?--test needs a test file name}"
            shift 2
            ;;
        --timeout)
            TIMEOUT="${2:?--timeout needs a number of seconds}"
            shift 2
            ;;
        --integration|-i)
            RUN_INTEGRATION=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v        Show verbose output"
            echo "  --test, -t NAME      Run only the specified test"
            echo "  --timeout SECONDS    Set timeout per test (default: 120, or 900 with -i)"
            echo "  --integration, -i    Also run agent tests (slow, costs tokens)"
            echo "  --help, -h           Show this help"
            echo ""
            echo "Offline tests:"
            echo "  test-validate-skills.sh    scripts/validate-skills.py, the static contracts"
            echo "  test-runner.sh             this runner's own gates"
            echo "  test-agent-harness.sh      run_claude itself, against a fake CLI"
            echo "  test-onboarding-skill.sh   onboarding SKILL.md / rules.md policy regressions"
            echo "  test-onboarding-volume.sh  volume.py's command-line contract"
            echo "  test-generation-skill.sh   generation SKILL.md / rules.md / FIELDS.md policy"
            echo "  test-generation-script.sh  generate.py's command-line contract"
            echo "  test-eval-harness.sh       evals judge.sh + run-evals.sh, against fake CLIs"
            echo ""
            echo "Integration tests (use --integration):"
            echo "  test-onboarding-agent.sh   Real agent behaviour, needs the claude CLI"
            echo "  test-generation-agent.sh   Real agent behaviour, needs the claude CLI"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Offline tests: no network, no API key, no agent.
# The validator runs first: a broken static contract explains the behavioural
# failures downstream of it, so report it before them.
tests=(
    "test-validate-skills.sh"
    "test-runner.sh"
    "test-agent-harness.sh"
    "test-onboarding-skill.sh"
    "test-onboarding-volume.sh"
    "test-generation-skill.sh"
    "test-generation-script.sh"
    "test-eval-harness.sh"
)

# Integration tests: these drive a real agent.
integration_tests=(
    "test-onboarding-agent.sh"
    "test-generation-agent.sh"
)

if [ "$RUN_INTEGRATION" = true ]; then
    # Only the integration tests need the CLI — the offline suite must run without it.
    if ! command -v claude &> /dev/null; then
        echo "ERROR: --integration needs the Claude Code CLI, which is not on PATH"
        echo "Install it first: https://code.claude.com"
        exit 1
    fi
    echo "Claude version: $(claude --version 2>/dev/null || echo 'unknown')"
    echo ""
    tests+=("${integration_tests[@]}")
    TIMEOUT="${TIMEOUT:-900}"
fi

TIMEOUT="${TIMEOUT:-120}"

# Filter to specific test if requested. Membership is checked so a typo is an
# error, not a skip — and naming an integration test still requires -i, so the
# CLI guard above has run and a plain invocation stays offline.
if [ -n "$SPECIFIC_TEST" ]; then
    if printf '%s\n' "${integration_tests[@]}" | grep -qxF "$SPECIFIC_TEST" \
            && [ "$RUN_INTEGRATION" = false ]; then
        echo "ERROR: $SPECIFIC_TEST is an integration test — add --integration to run it"
        exit 1
    fi
    if ! printf '%s\n' "${tests[@]}" "${integration_tests[@]}" | grep -qxF "$SPECIFIC_TEST"; then
        echo "ERROR: unknown test: $SPECIFIC_TEST"
        echo "Use --help to list the test files"
        exit 1
    fi
    tests=("$SPECIFIC_TEST")
fi

# Track results
passed=0
failed=0
skipped=0

# Run each test
for test in "${tests[@]}"; do
    echo "----------------------------------------"
    echo "Running: $test"
    echo "----------------------------------------"

    test_path="$SCRIPT_DIR/$test"

    if [ ! -f "$test_path" ]; then
        echo "  [SKIP] Test file not found: $test"
        skipped=$((skipped + 1))
        continue
    fi

    start_time=$(date +%s)

    if [ "$VERBOSE" = true ]; then
        if timeout -k 10 "$TIMEOUT" bash "$test_path"; then
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            echo ""
            echo "  [PASS] $test (${duration}s)"
            passed=$((passed + 1))
        else
            exit_code=$?
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            echo ""
            if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
                echo "  [FAIL] $test (timeout after ${TIMEOUT}s)"
            else
                echo "  [FAIL] $test (${duration}s)"
            fi
            failed=$((failed + 1))
        fi
    else
        # Capture output for non-verbose mode
        if output=$(timeout -k 10 "$TIMEOUT" bash "$test_path" 2>&1); then
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            echo "  [PASS] (${duration}s)"
            passed=$((passed + 1))
        else
            exit_code=$?
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
                echo "  [FAIL] (timeout after ${TIMEOUT}s)"
            else
                echo "  [FAIL] (${duration}s)"
            fi
            echo ""
            echo "  Output:"
            echo "$output" | sed 's/^/    /'
            failed=$((failed + 1))
        fi
    fi

    echo ""
done

# Print summary
echo "========================================"
echo " Test Results Summary"
echo "========================================"
echo ""
echo "  Passed:  $passed"
echo "  Failed:  $failed"
echo "  Skipped: $skipped"
echo ""

if [ "$RUN_INTEGRATION" = false ]; then
    echo "Note: agent tests were not run. Use --integration to include them."
    echo ""
fi

# A skipped test is a listed file that has gone missing — coverage silently
# lost, which must fail the run, not decorate a green one.
if [ $failed -gt 0 ] || [ $skipped -gt 0 ]; then
    echo "STATUS: FAILED"
    exit 1
else
    echo "STATUS: PASSED"
    exit 0
fi
