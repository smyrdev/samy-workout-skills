#!/usr/bin/env bash
# Integration: asks a real agent about the generation skill and checks it picked
# up the rules that matter. Run with run-skill-tests.sh --integration.
#
# This test is non-deterministic by nature — it costs tokens, takes minutes, and
# asserts on prose. Keep the patterns at keyword level. If one proves flaky,
# loosen it; a test that fails every third run teaches nobody anything.
#
# Each prompt probes a rule with no deterministic proxy elsewhere in the suite.
# There is deliberately no prompt about the missing volume block: that rule is
# already pinned three ways offline (test-generation-script.sh asserts the exit
# code and the returned volume.py command, test-generation-skill.sh pins the
# prose, and the validator pins the config). A slow non-deterministic prompt is
# worth spending on the rules nothing else can reach.
#
# A note on negative assertions. rules.md phrases every prohibition as
# "never <verb>", so an agent summarising it quotes the forbidden phrase back
# and a naive assert_not_contains fails on a correct answer. A negative here has
# to be a phrase the source never uses — hence "here is your plan" rather than
# "fabricate" or "never".

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

cd "$REPO_ROOT"

echo "=== Generation Skill Agent Behaviour ==="
echo ""

echo "It knows what the skill writes and what it must leave alone"
output=$(run_claude "Read skills/generation/SKILL.md and skills/generation/rules.md. Do not run the skill and do not write anything. Which files does this skill write, and which files under a person's directory must it leave alone?" 90 "Read")
if assert_agent_responded "$?" "$output" "the write-boundary prompt"; then
    assert_contains "$output" "plans" "names the plans directory as what it writes"
    assert_contains "$output" "rules\.json" "names the rules file it may not write"
    assert_contains "$output" "programs\|profile\.json" "names the onboarding files it may not write"
fi
echo ""

echo "It shows the week before writing it"
output=$(run_claude "Read skills/generation/rules.md. Do not write anything. What must you show the person before the first plan file lands on disk?" 90 "Read")
if assert_agent_responded "$?" "$output" "the echo-before-writing prompt"; then
    assert_contains "$output" "allocated\|planned\|table" "shows the planned-versus-allocated table"
    assert_contains "$output" "warning" "surfaces every warning"
    assert_contains "$output" "path" "names the exact paths"
fi
echo ""

echo "It refuses to invent a plan when the dataset is unavailable"
output=$(run_claude "Read skills/generation/rules.md. Do not write anything. There is no datasets/ cache, no network, and git is unavailable. I still want a plan today. What do you do?" 90 "Read")
if assert_agent_responded "$?" "$output" "the dataset-unavailable prompt"; then
    assert_contains "$output" "stop\|cannot\|unable\|refus" "stops rather than improvising"
    assert_contains "$output" "clone\|datasets/" "names the cache it needs"
    assert_not_contains "$output" "here is your plan" "does not produce one anyway"
fi

finish_tests
