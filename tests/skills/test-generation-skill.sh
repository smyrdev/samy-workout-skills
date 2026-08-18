#!/usr/bin/env bash
# Prose regressions in the generation skill: a portable SKILL.md, a wrapper that
# points instead of forking, and the rules that stop a silent overwrite or a
# fabricated plan. All by literal grep.
#
# Deliberately narrower than test-onboarding-skill.sh. scripts/validate-skills.py
# already owns, for this skill: frontmatter shape, the AskUserQuestion / Bash /
# "the Write tool" vendor-tool scan, the absolute and Windows path patterns, the
# gym / bodyfat / session-minute / goal enum tokens, both example files against
# their schemas, assets/datasets.json and generate.config.json completeness, and
# generate.py --self-test. test-validate-skills.sh runs it as part of this
# suite. What is asserted below is what that validator cannot see.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

SKILL="$REPO_ROOT/skills/generation/SKILL.md"
RULES="$REPO_ROOT/skills/generation/references/rules.md"
FIELDS="$REPO_ROOT/docs/generation-fields.md"
EXAMPLE_RULES="$REPO_ROOT/skills/generation/assets/examples/rules.example.md"
DESCRIPTOR="$REPO_ROOT/skills/generation/assets/datasets.json"
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
assert_file_contains "$SKILL" "references/rules.md" "points at references/rules.md"
assert_file_contains "$SKILL" "assets/datasets.json" "points at the dataset registry"
assert_file_contains "$SKILL" "scripts/generate.py" "points at the generator"
assert_file_contains "$SKILL" "without \`--write\` first" "the flow checks before it writes"
assert_file_contains "$SKILL" "Check first, write second" "the gotcha names the order"
assert_file_contains "$SKILL" "scripts/generate.config.json" "points at the config"
assert_file_contains "$SKILL" "assets/schema/" "points at the schemas"
assert_file_contains "$SKILL" "docs/generation-fields.md" "points at the hand-editing guide"
assert_file_contains "$SKILL" "assets/examples/rules.example.md" "points at the rules sample"
assert_file_contains "$SKILL" "skills/onboarding/references/rules.md" \
    "reuses onboarding's profile resolution instead of forking it"
assert_file_contains "$SKILL" "profile/plans/" "names its only writable surface"
assert_file_contains "$SKILL" "never interview" "says it never interviews"
echo ""

echo "The wrapper is a pointer, not a fork"
assert_file_contains "$WRAPPER" "skills/generation/SKILL.md" "defers to the portable skill"
assert_file_contains "$WRAPPER" "Do not duplicate" "says not to duplicate the flow"
assert_file_contains "$WRAPPER" "Three bindings" "stays at three environment bindings"
assert_file_contains "$WRAPPER" "AskUserQuestion" "binds the question tool"
assert_file_contains "$WRAPPER" "Bash" "binds the shell for the clone and the script"
assert_file_contains "$WRAPPER" "scripts/generate.py" "binds the generator step"
assert_file_contains "$WRAPPER" "three times" "runs the generator three times: brief, check, write"
assert_file_contains "$WRAPPER" "stop after the echo" "binds the no-question-tool fallback to a stop"
assert_file_contains "$WRAPPER" "--dataset" "documents the dataset argument"
assert_file_not_contains "$WRAPPER" "upper_lower" "holds no enum values either"
assert_file_not_contains "$WRAPPER" "must_include_first" "holds no order rule names either"
echo ""

echo "references/rules.md keeps the write-ownership boundary"
assert_file_contains "$RULES" 'entire writable surface is `profile/plans/`.' \
    "plans/ is the whole writable surface"
assert_file_contains "$RULES" "**This skill reads it and never writes it.**" \
    "rules.md belongs to the person"
assert_file_contains "$RULES" "Never re-interviews. Profile changes go through onboarding." \
    "an interview is onboarding's job"
assert_file_contains "$RULES" "never committed to this repository" \
    "the dataset cache is never committed"
echo ""

echo "references/rules.md keeps one owner per number"
assert_file_contains "$RULES" "**Targets are never computed or adjusted here**" \
    "targets have exactly one owner"
assert_file_contains "$RULES" "Never computes or adjusts volume targets" \
    "and says so again in the never-do list"
assert_file_contains "$RULES" "volume.py --profile profile/profile.json" \
    "hands back the exact volume.py command"
assert_file_contains "$RULES" "never in the script and never in prose" \
    "tunables live in the config alone"
echo ""

echo "references/rules.md keeps the rules that stop a wrong plan"
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

echo "references/rules.md keeps the four things shown before any file lands"
assert_file_contains "$RULES" "planned-versus-allocated table" "shows the planned-versus-allocated table"
assert_file_contains "$RULES" "The **week itself**" "shows the week itself"
assert_file_contains "$RULES" "**Every warning**" "shows every warning"
assert_file_contains "$RULES" "The **exact paths** about to be written." "names the exact paths"
assert_file_contains "$RULES" "If they abandon here, write nothing." "an abandoned review writes nothing"
assert_file_contains "$RULES" "The echo ends the turn" "the echo is a turn boundary"
assert_file_contains "$RULES" "Three commands" "documents brief, check, write as three commands"
assert_file_contains "$RULES" "never a hand tally" "the planned column is the generator's number"
echo ""

echo "docs/generation-fields.md stays the hand-editing contract"
assert_file_contains "$FIELDS" '`## Heading` starts a section' "pins the heading syntax"
assert_file_contains "$FIELDS" '`- item` is one value' "pins the bullet syntax"
assert_file_contains "$FIELDS" 'is ignored' "prose is a note to self, not a rule"
for heading in "## Exclude exercises" "## Exclude equipment" "## Exclude movement groups" \
               "## Exclude muscles" "## Focus muscles" "## Must include" "## Order"; do
    assert_file_contains "$FIELDS" "$heading" "documents the $heading section"
    assert_file_contains "$EXAMPLE_RULES" "$heading" "the sample has the $heading section"
done
echo ""

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

echo "coaching.md says what is enforced and what is not"
# The file is judgment, not contract, so almost nothing here is pinned. These
# four claims are: they are what stops a later edit from quietly turning
# guidance into a gate, or a gate into guidance.
COACHING="$REPO_ROOT/skills/generation/references/coaching.md"
assert_file_contains "$COACHING" "Enforced: \`rep_floors\`" "names the one training rule with teeth"
assert_file_contains "$COACHING" "The script enforces almost none of it" "is honest about its own status"
assert_file_contains "$COACHING" "coaching-deferred.md" "points at the rules that need session logging"
assert_file_contains "$REPO_ROOT/skills/generation/references/coaching-deferred.md" "Out of scope for now."     "the deferred rules say why they are deferred"
assert_file_not_contains "$COACHING" "Fatigue index" "no rule that needs per-set history is in the coach's read path"
assert_file_contains "$COACHING" "say which one you followed and why" "requires a stated override"
assert_file_not_contains "$COACHING" "HARD CAP" "no rule claims a cap the script does not apply"

echo "The registries say where knowledge lives"
assert_file_contains "$DESCRIPTOR" "scripts/generate.py contains none of it" \
    "the descriptor claims all dataset knowledge"
assert_file_contains "$CONFIG" "never in generate.py, SKILL.md, or CLAUDE.md" \
    "the config claims every tunable number"

finish_tests
