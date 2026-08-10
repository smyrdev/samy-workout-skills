#!/usr/bin/env bash
# Prose regressions in the generation skill: a portable SKILL.md, a wrapper that
# points instead of forking, and the rules that stop a silent overwrite or a
# fabricated plan. All by literal grep.
#
# Deliberately narrower than test-onboarding-skill.sh. scripts/validate-skills.py
# already owns, for this skill: frontmatter shape, the AskUserQuestion / Bash /
# "the Write tool" vendor-tool scan, the absolute and Windows path patterns, the
# gym / bodyfat / session-minute / goal enum tokens, both example files against
# their schemas, datasets.json and generate.config.json completeness, and
# generate.py --self-test. test-validate-skills.sh runs it as part of this
# suite. What is asserted below is what that validator cannot see.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

SKILL="$REPO_ROOT/skills/generation/SKILL.md"
RULES="$REPO_ROOT/skills/generation/rules.md"
FIELDS="$REPO_ROOT/skills/generation/FIELDS.md"
DESCRIPTOR="$REPO_ROOT/skills/generation/datasets.json"
CONFIG="$REPO_ROOT/skills/generation/scripts/generate.config.json"
WRAPPER="$REPO_ROOT/.claude/skills/generate/SKILL.md"

echo "=== Generation Skill Policy ==="
echo ""

echo "SKILL.md stays portable"
assert_file_not_contains "$SKILL" "allowed-tools:" "frontmatter carries no tool list"
assert_file_not_contains "$SKILL" "argument-hint:" "frontmatter carries no argument hint"
assert_file_not_contains "$SKILL" "Claude" "no vendor names"
assert_file_not_contains "$SKILL" "Anthropic" "no vendor names"
assert_file_not_contains "$SKILL" ".claude/" "no vendor directories"
assert_file_not_contains "$SKILL" "Glob" "no vendor tool names"
assert_file_not_contains "$SKILL" "Grep" "no vendor tool names"
echo ""

echo "SKILL.md holds no rule content"
assert_file_not_contains "$SKILL" "upper_lower" "holds no split enum values"
assert_file_not_contains "$SKILL" "full_body" "holds no split enum values"
assert_file_not_contains "$SKILL" "hamstrings" "holds no muscle group names"
assert_file_not_contains "$SKILL" "must_include_first" "holds no order rule names"
assert_file_not_contains "$SKILL" "indirect_discount" "holds no tunable numbers or their keys"
echo ""

echo "SKILL.md stays a set of pointers"
assert_file_contains "$SKILL" "rules.md" "points at rules.md"
assert_file_contains "$SKILL" "datasets.json" "points at the dataset registry"
assert_file_contains "$SKILL" "scripts/generate.py" "points at the generator"
assert_file_contains "$SKILL" "scripts/generate.config.json" "points at the config"
assert_file_contains "$SKILL" "schema/" "points at the schemas"
assert_file_contains "$SKILL" "FIELDS.md" "points at the hand-editing guide"
assert_file_contains "$SKILL" "examples/rules.example.json" "points at the rules sample"
assert_file_contains "$SKILL" "skills/onboarding/rules.md" \
    "reuses onboarding's profile resolution instead of forking it"
assert_file_contains "$SKILL" "profiles/<slug>/plans/" "names its only writable surface"
assert_file_contains "$SKILL" "never interview" "says it never interviews"
echo ""

echo "The wrapper is a pointer, not a fork"
assert_file_contains "$WRAPPER" "skills/generation/SKILL.md" "defers to the portable skill"
assert_file_contains "$WRAPPER" "Do not duplicate" "says not to duplicate the flow"
assert_file_contains "$WRAPPER" "Three bindings" "stays at three environment bindings"
assert_file_contains "$WRAPPER" "AskUserQuestion" "binds the question tool"
assert_file_contains "$WRAPPER" "Bash" "binds the shell for the clone and the script"
assert_file_contains "$WRAPPER" "scripts/generate.py" "binds the generator step"
assert_file_contains "$WRAPPER" "--dataset" "documents the dataset argument"
assert_file_not_contains "$WRAPPER" "upper_lower" "holds no enum values either"
assert_file_not_contains "$WRAPPER" "must_include_first" "holds no order rule names either"
echo ""

echo "rules.md keeps the write-ownership boundary"
assert_file_contains "$RULES" 'Its entire writable surface is `profiles/<slug>/plans/`.' \
    "plans/ is the whole writable surface"
assert_file_contains "$RULES" "**This skill reads it and never writes it.**" \
    "rules.json belongs to the person"
assert_file_contains "$RULES" "Never re-interviews. Profile changes go through onboarding." \
    "an interview is onboarding's job"
assert_file_contains "$RULES" "never committed to this repository" \
    "the dataset cache is never committed"
echo ""

echo "rules.md keeps one owner per number"
assert_file_contains "$RULES" "**Targets are never computed or adjusted here**" \
    "targets have exactly one owner"
assert_file_contains "$RULES" "Never computes or adjusts volume targets" \
    "and says so again in the never-do list"
assert_file_contains "$RULES" "volume.py --profile profiles/<slug>/profile.json" \
    "hands back the exact volume.py command"
assert_file_contains "$RULES" "never in the script and never in prose" \
    "tunables live in the config alone"
echo ""

echo "rules.md keeps the rules that stop a wrong plan"
assert_file_contains "$RULES" "never generate from memory of what the dataset probably contains." \
    "never invents exercises"
assert_file_contains "$RULES" "git clone --depth 1 --branch <ref> <repo> datasets/<name>" \
    "gives the exact clone command"
assert_file_contains "$RULES" "missing plan is recoverable; a plausible-looking wrong one is not." \
    "prefers no plan to a wrong one"
assert_file_contains "$RULES" "never silently drop a rule" "unmatched rules are surfaced"
assert_file_contains "$RULES" "Never hides a shortfall" "a shortfall is always reported"
assert_file_contains "$RULES" 'suffix `-2`, then `-3`' "a same-day re-run gets a suffix, not an overwrite"
assert_file_contains "$RULES" "hand-edit an exercise into the generator's output" \
    "a swap is a re-run, not an edit"
echo ""

echo "rules.md keeps the four things shown before any file lands"
assert_file_contains "$RULES" "planned-versus-allocated table" "shows the planned-versus-allocated table"
assert_file_contains "$RULES" "The **week itself**" "shows the week itself"
assert_file_contains "$RULES" "**Every warning**" "shows every warning"
assert_file_contains "$RULES" "The **exact paths** about to be written." "names the exact paths"
assert_file_contains "$RULES" "If they abandon here, write nothing." "an abandoned review writes nothing"
echo ""

echo "FIELDS.md stays the hand-editing contract"
assert_file_contains "$FIELDS" 'Always the quoted string `"1.0"`' "pins the schema version"
assert_file_contains "$FIELDS" "unknown_exclude_exercise:<name>" "names the unknown-exclusion warning"
assert_file_contains "$FIELDS" "unmatched_must_include:<name>" "names the unplaceable-must-include warning"
assert_file_contains "$FIELDS" '`chest`, `back`, `shoulders`, `biceps`, `triceps`,' "lists the muscle groups"
assert_file_contains "$FIELDS" '`quads`, `hamstrings`, `glutes`, `calves`,' "lists the rest of them"
assert_file_contains "$FIELDS" '`must_include_first`' "documents the order rule"
assert_file_contains "$FIELDS" '`trailer_groups_last`' "documents the order rule"
assert_file_contains "$FIELDS" '`compound_before_isolation`' "documents the order rule"
assert_file_contains "$FIELDS" '`focus_muscles_first`' "documents the order rule"
assert_file_contains "$FIELDS" '`large_groups_before_small`' "documents the order rule"
assert_file_contains "$FIELDS" "generated, not hand-written" "the plan JSON is not for hand-editing"
echo ""

echo "The registries say where knowledge lives"
assert_file_contains "$DESCRIPTOR" "scripts/generate.py contains none of it" \
    "the descriptor claims all dataset knowledge"
assert_file_contains "$CONFIG" "never in generate.py, SKILL.md, or CLAUDE.md" \
    "the config claims every tunable number"

finish_tests
