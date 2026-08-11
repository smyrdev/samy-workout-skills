#!/usr/bin/env bash
# Exercises skills/generation/scripts/generate.py through its real command line:
# exit codes, the refusals, the files it writes, the markdown render.
#
# --self-test runs generate_plan() in process against the bundled fixture. It
# never touches argv, never writes a file, and never calls render_markdown().
# Everything below is what that cannot see. The ten invariants it does cover
# (category filter, equipment tier, benchmark gates, ordering, split separation,
# deload) are not re-asserted here — validate-skills.py runs --self-test, and
# test-validate-skills.sh wires that into this suite.
#
# Two notes for anyone editing this file on Windows:
#   1. Paths must reach python as argv entries so the shell can translate them.
#      A path written literally inside a `python -c` body will not open.
#   2. A plan contains an emoji, so printing one to a cp1252 console raises
#      UnicodeEncodeError — every call goes through run_generate, which sets
#      PYTHONIOENCODING. Error messages contain em-dashes and the volume table
#      contains "×" and "⚠️": grep the ASCII part of those lines, never the
#      punctuation.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

GENERATE="$REPO_ROOT/skills/generation/scripts/generate.py"
FIXTURE="$REPO_ROOT/skills/generation/scripts/generate.fixture.json"
DESCRIPTOR="$REPO_ROOT/skills/generation/datasets.json"
CONFIG="$REPO_ROOT/skills/generation/scripts/generate.config.json"
PROFILE="$REPO_ROOT/skills/onboarding/examples/profile.example.json"
PROGRAM="$REPO_ROOT/skills/onboarding/examples/program.example.json"
PLAN_EXAMPLE="$REPO_ROOT/skills/generation/examples/plan.example.json"
TODAY="2026-08-06"

PROJECT=$(create_test_project)
trap 'cleanup_test_project "$PROJECT"' EXIT

# The dataset this whole file runs against: the bundled self-test fixture, laid
# out where the descriptor's data_file expects it. Offline, and the same input
# that produced examples/plan.example.json. Never datasets/ — that cache is
# gitignored, may be absent, and moves with upstream.
mkdir -p "$PROJECT/data"
cp "$FIXTURE" "$PROJECT/data/exercises.json"

# A profile plus a program file with no volume block — the state onboarding
# leaves behind before its last step.
create_test_profile "$PROJECT" "$REPO_ROOT" > /dev/null
NO_VOLUME_PROGRAM="$PROJECT/programs/program-2026-08-06.json"

# Run generate.py, capturing stdout+stderr in $out and the exit code in $code.
run_generate() {
    out=$(PYTHONIOENCODING=utf-8 python "$GENERATE" "$@" 2>&1)
    code=$?
}

# The common form: profile, program and the fixture dataset already filled in.
run_default() {
    run_generate --profile "$PROFILE" --program "$PROGRAM" \
        --dataset-dir "$PROJECT" --today "$TODAY" "$@"
}

# Read $1, apply the python statement in $3 to `d`, write $2. Paths travel as
# argv so the shell translates them; never put one inside $3.
doctor() {
    python -c "
import sys, json
d = json.load(open(sys.argv[1], encoding='utf-8'))
$3
json.dump(d, open(sys.argv[2], 'w', encoding='utf-8'))
" "$1" "$2"
}

# Print just the exercise names a plan chose. Needed because a plan echoes
# rules_applied verbatim, so grepping the whole JSON for an excluded name
# always matches its own exclusion entry.
plan_names() {
    PYTHONIOENCODING=utf-8 python -c "
import sys, json
p = json.load(open(sys.argv[1], encoding='utf-8'))
print('\n'.join(e['name'] for s in p['sessions'] for e in s['exercises']))
" "$1"
}

echo "=== Generation Script ==="
echo ""

echo "Self-test"
run_generate --self-test
assert_exit_code 0 "$code" "--self-test succeeds"
assert_contains "$out" "invariant groups hold" "--self-test reports its invariant groups"
assert_contains "$out" "exercises-dataset" "--self-test names the dataset it ran against"
echo ""

echo "Worked case reproduces the shipped example"
run_default --write "$PROJECT/plan.json" --write-md "$PROJECT/plan.md"
assert_exit_code 0 "$code" "generates a plan"
assert_count "$out" "^wrote " 2 "reports both files it wrote"

# Guard before the byte comparison: dataset.commit is the one environment-
# dependent field, and a temp dir inside a git worktree would fail the cmp for
# a reason that has nothing to do with the generator.
if python -c "
import sys, json
p = json.load(open(sys.argv[1], encoding='utf-8'))
sys.exit(0 if p['dataset']['commit'] is None else 1)
" "$PROJECT/plan.json"; then
    _pass "the temp dataset dir is outside a git worktree (dataset.commit is null)"
else
    _fail "the temp dataset dir is outside a git worktree (dataset.commit is null)"
    echo "    the byte comparison below cannot hold with a non-null commit"
fi

# Line endings are stripped on both sides: what the generator writes depends
# on the platform (text mode), and what the checkout holds depends on
# core.autocrlf — neither difference is the generator's doing.
if cmp -s <(tr -d '\r' < "$PROJECT/plan.json") <(tr -d '\r' < "$PLAN_EXAMPLE"); then
    _pass "reproduces examples/plan.example.json byte for byte"
else
    _fail "reproduces examples/plan.example.json byte for byte"
    diff <(tr -d '\r' < "$PLAN_EXAMPLE") <(tr -d '\r' < "$PROJECT/plan.json") | head -40 | sed 's/^/    /'
fi
echo ""

echo "Markdown render"
MD="$PROJECT/plan.md"
assert_file_contains "$MD" "## Weekly volume" "renders the volume table"
assert_file_contains "$MD" "| Muscle group | Allocated sets | Planned sets | |" \
    "the volume table has the planned-versus-allocated columns"
assert_file_contains "$MD" "## Day 1" "renders day 1"
assert_file_contains "$MD" "## Day 6" "renders every day the program asked for"
assert_file_contains "$MD" "| Exercise | Equipment | Sets " "each day has an exercise table"
assert_file_contains "$MD" "**Deload:**" "a deload program gets a deload note"
assert_file_contains "$MD" "Edit freely" "closes by telling the person the file is theirs"
assert_file_contains "$MD" "regenerate rather than hand-syncing the two" \
    "points back at regeneration, not hand-editing"
assert_file_not_contains "$MD" "## Warnings" "a clean run renders no warnings section"
echo ""

echo "Without --write the plan goes to stdout"
run_default
assert_exit_code 0 "$code" "prints the plan when --write is absent"
assert_contains "$out" '"sessions"' "stdout is the plan JSON"
assert_contains "$out" '"name": "Samy"' "carries the user's name from the profile"
assert_contains "$out" '"commit": null' "records a null commit for a non-git dataset dir"
assert_order "$out" '"chest"' '"back"' "targets are in canonical order (chest before back)"
assert_order "$out" '"calves"' '"core"' "targets are in canonical order (calves before core)"
first="$out"
echo ""

echo "Determinism"
run_default
if [ "$first" = "$out" ]; then
    _pass "two identical runs produce identical output"
else
    _fail "two identical runs produce identical output"
fi
echo ""

echo "Plans are never overwritten"
run_default --write "$PROJECT/plan.json"
assert_exit_code 2 "$code" "--write refuses an existing file"
assert_contains "$out" "already exists" "says the file already exists"
assert_contains "$out" "never overwritten" "says plans are never overwritten"
assert_contains "$out" "pick the next" "names the suffix convention"
run_default --write "$PROJECT/plan-2.json" --write-md "$PROJECT/plan.md"
assert_exit_code 2 "$code" "--write-md refuses an existing file"
assert_contains "$out" "already exists" "says the markdown file already exists"
assert_file_absent "$PROJECT/plan-2.json" \
    "a refused run writes neither file — no orphan plan JSON"
echo ""

echo "Usage errors exit 2"
run_generate
assert_exit_code 2 "$code" "--profile is required"
assert_contains "$out" "\-\-profile is required" "names the missing flag"
run_generate --profile "$PROFILE"
assert_exit_code 2 "$code" "--program is required"
assert_contains "$out" "\-\-program is required" "names the missing flag"
run_generate --profile "$PROFILE" --program "$PROGRAM"
assert_exit_code 2 "$code" "--dataset-dir is required"
assert_contains "$out" "\-\-dataset\-dir is required" "names the missing flag"
run_default --today "not-a-date"
assert_exit_code 2 "$code" "--today must be a real date"
assert_contains "$out" "not a valid YYYY-MM-DD" "says what a date looks like"
echo ""

echo "A broken config or descriptor is reported before the missing flags"
run_generate --descriptor "$PROJECT/no-such-descriptor.json"
assert_exit_code 3 "$code" "a missing descriptor is an input error"
assert_contains "$out" "descriptor not found" "names what is missing"
run_generate --config "$PROJECT/no-such-config.json"
assert_exit_code 3 "$code" "a missing config is an input error"
assert_contains "$out" "config not found" "names what is missing"
echo ""

echo "Input errors exit 3, never a guess"
run_generate --profile "$PROJECT/nope.json" --program "$PROGRAM" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a missing profile is an input error"
assert_contains "$out" "profile not found" "names the missing file"

run_generate --profile "$PROFILE" --program "$PROJECT/nope.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a missing program file is an input error"
assert_contains "$out" "program file not found" "names the missing file"

run_default --rules "$PROJECT/nope.json"
assert_exit_code 3 "$code" "a missing rules file is an input error"
assert_contains "$out" "rules file not found" "names the missing file"

run_generate --profile "$PROFILE" --program "$PROGRAM" --dataset-dir "$PROJECT/data"
assert_exit_code 3 "$code" "a dataset dir without the descriptor's data file is refused"
assert_contains "$out" "dataset data file not found" "says which kind of file is missing"

run_default --dataset bogus
assert_exit_code 3 "$code" "an unknown --dataset name is refused"
assert_contains "$out" "unknown dataset 'bogus'" "names the value it does not know"
assert_contains "$out" "exercises-dataset" "lists the names it does know"

printf '{' > "$PROJECT/broken.json"
run_generate --profile "$PROFILE" --program "$PROJECT/broken.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "malformed JSON is an input error"
assert_contains "$out" "is not valid JSON" "says the file is not valid JSON"

mkdir -p "$PROJECT/objset/data"
printf '{}' > "$PROJECT/objset/data/exercises.json"
run_generate --profile "$PROFILE" --program "$PROGRAM" --dataset-dir "$PROJECT/objset"
assert_exit_code 3 "$code" "a dataset data file that is not an array is refused"
assert_contains "$out" "not an array of records" "says what shape it expected"
echo ""

echo "The volume block belongs to volume.py, and the generator says so"
run_generate --profile "$PROFILE" --program "$NO_VOLUME_PROGRAM" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a program file with no volume block is refused"
assert_contains "$out" "no volume block" "says what is missing"
assert_contains "$out" "volume.py --profile" "hands back the volume.py command"

doctor "$PROGRAM" "$PROJECT/null-volume.json" "d['volume'] = None"
run_generate --profile "$PROFILE" --program "$PROJECT/null-volume.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a null volume block is refused the same way"
assert_contains "$out" "no volume block" "says what is missing"

run_generate --profile "$PROFILE" --program "$PROFILE" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a file with no program object is refused"
assert_contains "$out" "no .program. object" "says which object is missing"
echo ""

# A hand-edited program file can be present but incomplete. FIELDS.md teaches
# people to edit these files, so a half-written one is an expected input, not
# programmer error — it has to come back as an input error naming the missing
# key, never as a traceback. An agent that meets an unexplained crash here is
# the one most likely to improvise a volume block, which is the single thing
# this repository forbids hardest.
echo "An incomplete program file is refused, not crashed on"
doctor "$PROGRAM" "$PROJECT/empty-volume.json" "d['volume'] = {}"
run_generate --profile "$PROFILE" --program "$PROJECT/empty-volume.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "an empty volume block is an input error"
assert_contains "$out" "volume block missing keys" "names the shape it wanted"
assert_contains "$out" "equipment_tier" "names a missing key"
assert_contains "$out" "volume.py" "hands back the command that rebuilds it"

doctor "$PROGRAM" "$PROJECT/partial-volume.json" "del d['volume']['per_muscle_weekly_sets']"
run_generate --profile "$PROFILE" --program "$PROJECT/partial-volume.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a volume block missing one key is an input error"
assert_contains "$out" "per_muscle_weekly_sets" "names the missing key"

doctor "$PROGRAM" "$PROJECT/empty-program.json" "d['program'] = {}"
run_generate --profile "$PROFILE" --program "$PROJECT/empty-program.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "an empty program block is an input error"
assert_contains "$out" "program block missing keys" "names the shape it wanted"
assert_contains "$out" "split" "names a missing key"

# The guard must cover every key the plan echo needs, not just the ones the
# fitting code reads: emoji is only touched by the markdown render, so with a
# narrower guard this run exits 0 and writes a plan.json that plan.schema.json
# rejects — or a KeyError once --write-md joins in.
doctor "$PROGRAM" "$PROJECT/no-emoji.json" "del d['program']['emoji']"
run_generate --profile "$PROFILE" --program "$PROJECT/no-emoji.json" --dataset-dir "$PROJECT"
assert_exit_code 3 "$code" "a program block missing a render-only key is an input error"
assert_contains "$out" "emoji" "names the missing key"

echo ""

echo "Unknown dataset vocabulary is refused, never guessed"
doctor "$DESCRIPTOR" "$PROJECT/d-unmapped.json" \
    "del d['datasets']['exercises-dataset']['muscle_map']['Chest']"
run_default --descriptor "$PROJECT/d-unmapped.json"
assert_exit_code 3 "$code" "an unmapped dataset muscle is refused"
assert_contains "$out" "muscles not in muscle_map/muscle_ignore" "names the mapping tables"

doctor "$DESCRIPTOR" "$PROJECT/d-untiered.json" \
    "d['datasets']['exercises-dataset']['equipment_tiers']['1'].remove('dumbbell')"
run_default --descriptor "$PROJECT/d-untiered.json"
assert_exit_code 3 "$code" "an untiered equipment value is refused"
assert_contains "$out" "equipment not in any tier" "names the problem"
assert_contains "$out" "equipment_tiers in datasets.json" "names the file to fix"

doctor "$DESCRIPTOR" "$PROJECT/d-dup.json" \
    "d['datasets']['exercises-dataset']['equipment_tiers']['2'].append('barbell')"
run_default --descriptor "$PROJECT/d-dup.json"
assert_exit_code 3 "$code" "equipment in two tiers is refused"
assert_contains "$out" "appears in more than one tier" "says how it is ambiguous"

doctor "$DESCRIPTOR" "$PROJECT/d-incomplete.json" \
    "del d['datasets']['exercises-dataset']['muscle_ignore']"
run_default --descriptor "$PROJECT/d-incomplete.json"
assert_exit_code 3 "$code" "an incomplete descriptor entry is refused"
assert_contains "$out" "missing keys" "says the entry is incomplete"
assert_contains "$out" "muscle_ignore" "names the missing key"

doctor "$DESCRIPTOR" "$PROJECT/d-empty.json" "d['datasets'] = {}"
run_default --descriptor "$PROJECT/d-empty.json"
assert_exit_code 3 "$code" "a descriptor with no datasets is refused"
assert_contains "$out" "descriptor has no datasets" "says the descriptor is empty"

doctor "$PROFILE" "$PROJECT/no-benchmark.json" "del d['strength_benchmarks']['dips_10']"
run_generate --profile "$PROJECT/no-benchmark.json" --program "$PROGRAM" \
    --dataset-dir "$PROJECT" --today "$TODAY"
assert_exit_code 3 "$code" "a profile missing a gated benchmark is refused"
assert_contains "$out" "strength_benchmarks missing key" "names the profile field"
assert_contains "$out" "benchmark_gates" "names the descriptor section that asked for it"
echo ""

echo "Every tunable number lives in the config"
doctor "$CONFIG" "$PROJECT/c-incomplete.json" "del d['reps_by_goal']"
run_default --config "$PROJECT/c-incomplete.json"
assert_exit_code 3 "$code" "an incomplete config is refused"
assert_contains "$out" "config missing keys" "says the config is incomplete"
assert_contains "$out" "reps_by_goal" "names the missing key"

doctor "$PROGRAM" "$PROJECT/p-split.json" "d['program']['split'] = 'ppl'"
run_generate --profile "$PROFILE" --program "$PROJECT/p-split.json" \
    --dataset-dir "$PROJECT" --today "$TODAY"
assert_exit_code 3 "$code" "an unknown split is refused"
assert_contains "$out" "unknown split" "names the value"
assert_contains "$out" "split_sessions in generate.config.json" "points at the config, not the script"

doctor "$PROGRAM" "$PROJECT/p-goal.json" "d['program']['primary_goal'] = 'powerlifting'"
run_generate --profile "$PROFILE" --program "$PROJECT/p-goal.json" \
    --dataset-dir "$PROJECT" --today "$TODAY"
assert_exit_code 3 "$code" "an unknown goal is refused"
assert_contains "$out" "unknown goal" "names the value"
assert_contains "$out" "reps_by_goal in generate.config.json" "points at the config, not the script"

doctor "$PROGRAM" "$PROJECT/p-tier0.json" "d['volume']['equipment_tier'] = 0"
run_generate --profile "$PROFILE" --program "$PROJECT/p-tier0.json" \
    --dataset-dir "$PROJECT" --today "$TODAY"
assert_exit_code 3 "$code" "an empty candidate set is refused rather than planned around"
assert_contains "$out" "no exercises left after filtering" "says why there is nothing to plan"
echo ""

echo "Personal rules are honoured or refused, never silently dropped"
printf '%s' '{"exclude": {"exercizes": []}}' > "$PROJECT/r-typo.json"
run_default --rules "$PROJECT/r-typo.json"
assert_exit_code 3 "$code" "a mistyped rules key is refused"
assert_contains "$out" "unknown key 'exercizes'" "quotes the key back"

printf '%s' '{"exclude": {"muscles": ["neck"]}}' > "$PROJECT/r-muscle.json"
run_default --rules "$PROJECT/r-muscle.json"
assert_exit_code 3 "$code" "an unknown muscle group is refused"
assert_contains "$out" "unknown muscle group 'neck'" "quotes the group back"
assert_contains "$out" "valid groups" "lists the groups it accepts"

printf '%s' '{"order": ["alphabetical"]}' > "$PROJECT/r-order.json"
run_default --rules "$PROJECT/r-order.json"
assert_exit_code 3 "$code" "an unknown order rule is refused"
assert_contains "$out" "unknown order rule 'alphabetical'" "quotes the rule back"
assert_contains "$out" "valid rules" "lists the rules it accepts"

# A rule that matches nothing is a warning, not a failure, and it reaches the
# person through both outputs.
printf '%s' '{"exclude": {"exercises": ["flying pig"], "equipment": ["jetpack"], "movement_groups": ["levitation"]}, "focus": {"must_include": ["flying pig"]}}' \
    > "$PROJECT/r-unknowns.json"
run_default --rules "$PROJECT/r-unknowns.json" --write-md "$PROJECT/warned.md"
assert_exit_code 0 "$code" "unmatched rule entries are a warning, not a failure"
assert_contains "$out" "unknown_exclude_exercise:flying pig" "warns about the unknown exercise"
assert_contains "$out" "unknown_exclude_equipment:jetpack" "warns about the unknown equipment"
assert_contains "$out" "unknown_exclude_movement_group:levitation" "warns about the unknown movement group"
assert_contains "$out" "unmatched_must_include:flying pig" "warns about the unplaceable must-include"
assert_file_contains "$PROJECT/warned.md" "## Warnings" "the render carries a warnings section"
assert_file_contains "$PROJECT/warned.md" "unknown_exclude_exercise:flying pig" "the render names the warning"

printf '%s' '{"exclude": {"exercises": ["barbell bench press"]}}' > "$PROJECT/r-excl.json"
run_default --rules "$PROJECT/r-excl.json" --write "$PROJECT/plan-excl.json"
assert_exit_code 0 "$code" "an exclusion runs clean"
assert_not_contains "$(plan_names "$PROJECT/plan-excl.json")" "barbell bench press" \
    "the excluded exercise is gone from every session"

printf '%s' '{"focus": {"must_include": ["dumbbell fly"]}}' > "$PROJECT/r-must.json"
run_default --rules "$PROJECT/r-must.json" --write "$PROJECT/plan-must.json"
assert_exit_code 0 "$code" "a must-include runs clean"
assert_contains "$(plan_names "$PROJECT/plan-must.json")" "dumbbell fly" \
    "the pinned exercise is in the week"
echo ""

echo "A shortfall is never hidden"
doctor "$PROGRAM" "$PROJECT/p-short.json" \
    "d['volume']['per_muscle_weekly_sets']['hamstrings'] = 60; d['volume']['exercises_per_session'] = 3"
run_generate --profile "$PROFILE" --program "$PROJECT/p-short.json" \
    --dataset-dir "$PROJECT" --today "$TODAY" --write-md "$PROJECT/short.md"
assert_exit_code 0 "$code" "an unreachable allocation still produces a plan"
assert_contains "$out" "short:hamstrings" "the plan reports the shortfall"
assert_file_contains "$PROJECT/short.md" " short |" "the render flags the short row"

finish_tests
