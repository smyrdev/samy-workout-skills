#!/usr/bin/env bash
# Regression check: the onboarding skill's prose keeps the promises the rest of
# the repository relies on — a thin, vendor-neutral SKILL.md, a wrapper that
# points instead of forking, and the rules that stop a silent overwrite.
#
# Schema validity, questions.yaml `stores:` resolution and volume.config.json
# enum coverage are NOT checked here — scripts/validate-skills.py owns those.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

SKILL="$REPO_ROOT/skills/onboarding/SKILL.md"
RULES="$REPO_ROOT/skills/onboarding/rules.md"
QUESTIONS="$REPO_ROOT/skills/onboarding/questions.yaml"
WRAPPER="$REPO_ROOT/.claude/skills/onboard/SKILL.md"

echo "=== Onboarding Skill Policy ==="
echo ""

echo "SKILL.md is portable"
assert_file_not_contains "$SKILL" "allowed-tools:" "frontmatter carries no tool list"
assert_file_not_contains "$SKILL" "argument-hint:" "frontmatter carries no argument hint"
assert_file_not_contains "$SKILL" "AskUserQuestion" "no vendor tool names"
assert_file_not_contains "$SKILL" "Claude" "no vendor names"
assert_file_not_contains "$SKILL" ".claude/" "no vendor directories"
assert_file_not_contains "$SKILL" "C:\\" "no Windows paths"
assert_file_not_contains "$SKILL" "/Users/" "no absolute paths"
echo ""

echo "SKILL.md stays a set of pointers"
assert_file_contains "$SKILL" "questions.yaml" "points at questions.yaml"
assert_file_contains "$SKILL" "rules.md" "points at rules.md"
assert_file_contains "$SKILL" "schema/profile.schema.json" "points at the profile schema"
assert_file_contains "$SKILL" "scripts/volume.py" "points at the volume script"
assert_file_not_contains "$SKILL" "upper_lower" "holds no split enum values"
assert_file_not_contains "$SKILL" "commercial_gym" "holds no gym enum values"
assert_file_not_contains "$SKILL" "13-17" "holds no bodyfat bracket values"
echo ""

echo "The .claude wrapper is a pointer, not a fork"
assert_file_contains "$WRAPPER" "skills/onboarding/SKILL.md" "defers to the portable skill"
assert_file_contains "$WRAPPER" "Do not duplicate" "says not to duplicate the flow"
assert_file_contains "$WRAPPER" "Three bindings" "stays at three environment bindings"
assert_file_contains "$WRAPPER" "AskUserQuestion" "binds the question tool"
assert_file_contains "$WRAPPER" "scripts/volume.py" "binds the volume step"
assert_file_not_contains "$WRAPPER" "upper_lower" "holds no enum values either"
echo ""

echo "rules.md keeps the safety rules"
assert_file_contains "$RULES" "no default profile and no last-used memory" "no default profile"
assert_file_contains "$RULES" "Echoing before writing is mandatory" "echo before write is mandatory"
assert_file_contains "$RULES" "never a full re-interview" "an update is not a re-interview"
assert_file_contains "$RULES" "skills/onboarding/examples/" "the shipped examples are off limits"
assert_file_contains "$RULES" "2.54" "inch conversion constant is exact"
assert_file_contains "$RULES" "0.45359237" "pound conversion constant is exact"
assert_file_contains "$RULES" 'left `null`' "documents the no-Python fallback"
echo ""

echo "questions.yaml keeps the profile/program scope split"
assert_file_contains "$QUESTIONS" "stores: basics.bodyfat_bracket" "bodyfat is a profile field"
assert_file_contains "$QUESTIONS" "stores: program.days_per_week" "days per week is a program field"
assert_file_contains "$QUESTIONS" "escape:" "choice questions offer an escape"

finish_tests
