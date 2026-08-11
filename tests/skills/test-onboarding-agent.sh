#!/usr/bin/env bash
# Integration: asks a real agent about the onboarding skill and checks it picked
# up the rules that matter. Run with run-skill-tests.sh --integration.
#
# This test is non-deterministic by nature — it costs tokens, takes minutes, and
# asserts on prose. Keep the patterns at keyword level. If one proves flaky,
# loosen it; a test that fails every third run teaches nobody anything.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

cd "$REPO_ROOT"

echo "=== Onboarding Skill Agent Behaviour ==="
echo ""

echo "It knows what the skill writes"
output=$(run_claude "Read skills/onboarding/SKILL.md and its pointers. Do not run the skill and do not write anything. Describe what onboarding does and which files it writes." 90 "Read")
if assert_agent_responded "$?" "$output" "the what-it-writes prompt"; then
    assert_contains "$output" "profile\.json" "names profile.json"
    assert_contains "$output" "program" "names the program file"
    assert_contains "$output" "volume" "mentions the volume step"
fi
echo ""

echo "It confirms before writing"
output=$(run_claude "Read skills/onboarding/SKILL.md and skills/onboarding/rules.md. Do not write anything. What must happen before the first byte is written?" 90 "Read")
if assert_agent_responded "$?" "$output" "the confirm-before-writing prompt"; then
    assert_contains "$output" "summary\|echo\|confirm" "echoes a summary first"
    assert_contains "$output" "path" "names the paths it is about to write"
fi
echo ""

echo "It resolves whose profile this is instead of assuming"
output=$(run_claude "Read skills/onboarding/rules.md. Do not write anything. Several profiles exist and I did not say who I am. What do you do?" 90 "Read")
if assert_agent_responded "$?" "$output" "the whose-profile prompt"; then
    assert_contains "$output" "ask\|which\|who" "asks who this is"
    assert_not_contains "$output" "assume the default profile" "does not assume a default"
fi

finish_tests
