#!/usr/bin/env bash
# Exercises skills/onboarding/scripts/volume.py through its real command line:
# exit codes, --write merging, determinism, and its refusal to guess.
#
# --self-test only covers compute_volume() in process; nothing below it is
# reachable that way.
#
# Note for anyone editing this file on Windows: paths must reach python as
# argv entries so the shell can translate them. A path written literally
# inside a `python -c` body is not translated and will not open.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

VOLUME="$REPO_ROOT/skills/onboarding/scripts/volume.py"
PROFILE="$REPO_ROOT/skills/onboarding/examples/profile.example.json"
PROGRAM="$REPO_ROOT/skills/onboarding/examples/program.example.json"
TODAY="2026-08-06"

PROJECT=$(create_test_project)
trap 'cleanup_test_project "$PROJECT"' EXIT
create_test_profile "$PROJECT" "$REPO_ROOT" > /dev/null
FIXTURE_PROGRAM="$PROJECT/programs/program-2026-08-06.json"

# Run volume.py, capturing stdout+stderr in $out and the exit code in $code.
run_volume() {
    out=$(python "$VOLUME" "$@" 2>&1)
    code=$?
}

echo "=== Onboarding Volume Script ==="
echo ""

echo "Self-test"
run_volume --self-test
assert_exit_code 0 "$code" "--self-test succeeds"
assert_contains "$out" "720 enum combinations" "--self-test covers every enum combination"
echo ""

echo "Worked case matches the shipped example"
run_volume --profile "$PROFILE" --goal hypertrophy --days 6 --session 60-90 \
    --split upper_lower --today "$TODAY"
assert_exit_code 0 "$code" "computes a volume block"
echo "$out" > "$PROJECT/computed.json"
if python -c "
import sys, json
got = json.load(open(sys.argv[1], encoding='utf-8'))
want = json.load(open(sys.argv[2], encoding='utf-8'))['volume']
sys.exit(0 if got == want else 1)
" "$PROJECT/computed.json" "$PROGRAM"; then
    _pass "output reproduces examples/program.example.json's volume block"
else
    _fail "output reproduces examples/program.example.json's volume block"
    echo "$out" | sed 's/^/    /'
fi
assert_order "$out" '"chest"' '"back"' "muscles are in canonical order (chest before back)"
assert_order "$out" '"calves"' '"core"' "muscles are in canonical order (calves before core)"
echo ""

echo "Determinism"
run_volume --profile "$PROFILE" --goal both --days 4 --session 40-60 \
    --split full_body --today "$TODAY"
first="$out"
run_volume --profile "$PROFILE" --goal both --days 4 --session 40-60 \
    --split full_body --today "$TODAY"
if [ "$first" = "$out" ]; then
    _pass "two identical runs produce identical output"
else
    _fail "two identical runs produce identical output"
fi
echo ""

echo "Usage errors exit 2"
run_volume --goal hypertrophy --days 6 --session 60-90 --split upper_lower
assert_exit_code 2 "$code" "--profile is required"
run_volume --profile "$PROFILE" --days 6 --session 60-90 --split upper_lower
assert_exit_code 2 "$code" "--goal is required without --write"
run_volume --profile "$PROFILE" --goal hypertrophy --days 6 --session 60-90 \
    --split upper_lower --today "not-a-date"
assert_exit_code 2 "$code" "--today must be a real date"
run_volume --profile "$PROFILE" --goal hypertrophy --days 6 --session 60-90 --split ppl
assert_exit_code 2 "$code" "an unknown --split value is rejected"
echo ""

echo "Input errors exit 3, never a guess"
run_volume --profile "$PROJECT/no-such-profile.json" --goal hypertrophy --days 6 \
    --session 60-90 --split upper_lower
assert_exit_code 3 "$code" "a missing profile is an input error"
assert_contains "$out" "profile not found" "says which file is missing"

python -c "
import sys, json
p = json.load(open(sys.argv[1], encoding='utf-8'))
p['gym']['type'] = 'space_station'
json.dump(p, open(sys.argv[2], 'w', encoding='utf-8'))
" "$PROFILE" "$PROJECT/bad-gym.json"
run_volume --profile "$PROJECT/bad-gym.json" --goal hypertrophy --days 6 \
    --session 60-90 --split upper_lower --today "$TODAY"
assert_exit_code 3 "$code" "an unknown gym type is refused"
assert_contains "$out" "gym.type" "names the offending field"

python -c "
import sys, json
p = json.load(open(sys.argv[1], encoding='utf-8'))
del p['experience']['lifting']
json.dump(p, open(sys.argv[2], 'w', encoding='utf-8'))
" "$PROFILE" "$PROJECT/no-lifting.json"
run_volume --profile "$PROJECT/no-lifting.json" --goal hypertrophy --days 6 \
    --session 60-90 --split upper_lower --today "$TODAY"
assert_exit_code 3 "$code" "a missing lifting experience is refused"
echo ""

echo "--write merges into a program file"
# Snapshot the program block so the comparison below needs no literals — the
# emoji in it does not survive a round trip through a command line.
dump_program() {
    python -c "
import sys, json
d = json.load(open(sys.argv[1], encoding='utf-8'))
json.dump(d['program'], open(sys.argv[2], 'w', encoding='utf-8'), sort_keys=True)
" "$1" "$2"
}
dump_program "$FIXTURE_PROGRAM" "$PROJECT/program-before.json"

run_volume --profile "$PROFILE" --write "$FIXTURE_PROGRAM" --today "$TODAY"
assert_exit_code 0 "$code" "reads goal/days/session/split from the program block"
assert_contains "$out" "wrote volume block to" "reports where it wrote"
assert_file_contains "$FIXTURE_PROGRAM" "per_muscle_weekly_sets" "the file now has a volume block"

dump_program "$FIXTURE_PROGRAM" "$PROJECT/program-after.json"
if cmp -s "$PROJECT/program-before.json" "$PROJECT/program-after.json"; then
    _pass "the program block is left untouched"
else
    _fail "the program block is left untouched"
fi

if python -c "
import sys, json
v = json.load(open(sys.argv[1], encoding='utf-8'))['volume']
sys.exit(0 if sum(v['per_muscle_weekly_sets'].values()) == v['weekly_sets_allocated'] else 1)
" "$FIXTURE_PROGRAM"; then
    _pass "the per-muscle sets sum to weekly_sets_allocated"
else
    _fail "the per-muscle sets sum to weekly_sets_allocated"
fi

finish_tests
