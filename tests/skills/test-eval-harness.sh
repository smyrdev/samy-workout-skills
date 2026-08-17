#!/usr/bin/env bash
# Covers evals/judge.py — the rubric-judging step of the eval pipeline.
#
# Offline and deterministic: CLAUDE_BIN points at fake CLIs, same trick as
# test-agent-harness.sh, so every failure path runs without spending a token.
#
# The one thing every fake must honor: the real CLI's --output-format json
# prints an ENVELOPE — a JSON object whose "result" field holds the judge's
# text as a string. The verdict JSON lives double-encoded inside it. A fake
# that printed the verdict directly would pass a parser the real CLI breaks.

set -uo pipefail
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

JUDGE="$REPO_ROOT/evals/judge.py"
RUNNER="$REPO_ROOT/evals/run-evals.sh"

PROJECT=$(create_test_project)
trap 'cleanup_test_project "$PROJECT"' EXIT

# --- inputs the judge receives -------------------------------------------
# Markers let assertions prove the one built prompt really contains all three.
cat > "$PROJECT/rubric.md" <<'EOF'
# Rubric RUBRIC-MARKER
Score the five criteria.
EOF
cat > "$PROJECT/persona.yaml" <<'EOF'
name: Testa
story: PERSONA-MARKER — likes short sessions.
EOF
cat > "$PROJECT/plan.md" <<'EOF'
# Plan PLAN-MARKER
Day 1: squat, push-up.
EOF

# --- canned verdicts, generated rather than hand-escaped ------------------
# Nested JSON-in-JSON is exactly the thing not to write by hand.
python - "$PROJECT" <<'EOF'
import json, sys, pathlib
proj = pathlib.Path(sys.argv[1])
names = ["selection_suitability", "balance_and_coverage",
         "ordering_and_structure", "persona_fit", "red_flags"]

def verdict(scores):
    crits = [{"name": n, "evidence": f"evidence for {n}",
              "reasoning": f"reasoning for {n}", "score": s}
             for n, s in zip(names, scores)]
    overall = round(sum(scores) / len(scores), 1)
    return {"criteria": crits, "red_flags": [], "overall": overall,
            "summary": "a fine plan overall"}

def envelope(v):
    return json.dumps({"result": json.dumps(v)})

(proj / "good-envelope.json").write_text(envelope(verdict([4, 4, 4, 4, 5])),
                                         encoding="utf-8")
# Three judges with varying scores for the median test:
#   criterion 1 scores 2/5/3 -> median 3, criterion 3 scores 3/4/5 -> median 4,
#   overalls 3.4/4.2/4.0 -> median 4.0. None equals a plain average.
for i, scores in enumerate(([2, 3, 3, 4, 5],
                            [5, 3, 4, 4, 5],
                            [3, 3, 5, 4, 5]), start=1):
    (proj / f"envelope-{i}.json").write_text(envelope(verdict(scores)),
                                             encoding="utf-8")
EOF

# --- fake CLIs ------------------------------------------------------------
# Each appends to its own log so the tests can pin exactly how many times the
# judge called the CLI — that log is the retry ladder made visible.
cat > "$PROJECT/ok" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/ok-calls.log"
cat "$PROJECT/good-envelope.json"
EOF
cat > "$PROJECT/garbage" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/garbage-calls.log"
echo "TOTALLY NOT JSON"
EOF
# Garbage on the first call, the good envelope after — the retry must recover.
cat > "$PROJECT/flaky" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/flaky-calls.log"
if [ ! -f "$PROJECT/flaky-ran" ]; then
    touch "$PROJECT/flaky-ran"
    echo "GARBAGE ON THE FIRST TRY"
else
    cat "$PROJECT/good-envelope.json"
fi
EOF
# Emits a different verdict per call, driven by its own call count.
cat > "$PROJECT/three" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/three-calls.log"
n=\$(wc -l < "$PROJECT/three-calls.log")
cat "$PROJECT/envelope-\$n.json"
EOF
# Ignores SIGTERM like the real CLI — the deadline must be enforced with a
# kill, not just reported. Same lesson test-agent-harness.sh pins.
cat > "$PROJECT/stubborn" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/stubborn-calls.log"
trap "" TERM
echo "FIXTURE-STUBBORN: ignoring TERM"
sleep 60
EOF
chmod +x "$PROJECT/ok" "$PROJECT/garbage" "$PROJECT/flaky" \
         "$PROJECT/three" "$PROJECT/stubborn"

judge() {  # judge <fake> <out-dir> [extra flags...]
    local fake="$1" out="$2"; shift 2
    CLAUDE_BIN="$PROJECT/$fake" python "$JUDGE" \
        "$PROJECT/rubric.md" "$PROJECT/persona.yaml" "$PROJECT/plan.md" \
        "$out" "$@"
}

calls() {  # calls <fake> -> how many times that fake ran
    if [ -f "$PROJECT/$1-calls.log" ]; then
        wc -l < "$PROJECT/$1-calls.log" | tr -d ' '
    else
        echo 0
    fi
}

echo "=== Eval Judge Harness ==="
echo ""

echo "A valid verdict is scored"
judge ok "$PROJECT/out-ok" > /dev/null 2>&1
rc=$?
assert_exit_code 0 "$rc" "a valid verdict exits 0"
assert_file_contains "$PROJECT/out-ok/verdict.json" '"outcome": "scored"' \
    "verdict.json says scored"
assert_file_contains "$PROJECT/out-ok/verdict.json" "selection_suitability" \
    "the criteria made it into the verdict"
assert_exit_code 1 "$(calls ok)" "one judging means one CLI call"
echo ""

echo "The one prompt holds rubric, persona, and plan"
assert_file_contains "$PROJECT/out-ok/prompt.txt" "RUBRIC-MARKER" \
    "the rubric is in the prompt"
assert_file_contains "$PROJECT/out-ok/prompt.txt" "PERSONA-MARKER" \
    "the persona is in the prompt"
assert_file_contains "$PROJECT/out-ok/prompt.txt" "PLAN-MARKER" \
    "the plan is in the prompt"
echo ""

echo "Garbage gets one retry, then a written indeterminate"
judge garbage "$PROJECT/out-garbage" > /dev/null 2>&1
rc=$?
assert_exit_code 1 "$rc" "give-up exits 1"
assert_exit_code 2 "$(calls garbage)" "the CLI was called exactly twice"
assert_file_contains "$PROJECT/out-garbage/verdict.json" \
    '"outcome": "indeterminate"' "the verdict file still lands, as indeterminate"
assert_file_contains "$PROJECT/out-garbage/response-j1-a2.json" \
    "TOTALLY NOT JSON" "the raw response is saved for the postmortem"
echo ""

echo "Garbage then valid — the retry recovers"
judge flaky "$PROJECT/out-flaky" > /dev/null 2>&1
rc=$?
assert_exit_code 0 "$rc" "a recovered judging exits 0"
assert_exit_code 2 "$(calls flaky)" "recovery took exactly two calls"
assert_file_contains "$PROJECT/out-flaky/verdict.json" '"outcome": "scored"' \
    "and the verdict is scored, not indeterminate"
echo ""

echo "The timeout is enforced, not just reported"
start=$(date +%s)
judge stubborn "$PROJECT/out-stubborn" --timeout 2 > /dev/null 2>&1
rc=$?
elapsed=$(( $(date +%s) - start ))
assert_exit_code 1 "$rc" "a timed-out judging exits 1"
assert_file_contains "$PROJECT/out-stubborn/verdict.json" \
    '"outcome": "indeterminate"' "a timeout is indeterminate, never a score"
assert_file_contains "$PROJECT/out-stubborn/verdict.json" "timed out" \
    "and the reason says so"
assert_exit_code 1 "$(calls stubborn)" \
    "a timeout is not retried — it would just time out again"
if [ "$elapsed" -lt 25 ]; then
    _pass "a CLI that ignores SIGTERM is killed near the deadline (${elapsed}s)"
else
    _fail "a CLI that ignores SIGTERM is killed near the deadline"
    echo "    budget was 2s, run took ${elapsed}s — reported, not enforced"
fi
echo ""

echo "--judges 3 takes the per-criterion median"
judge three "$PROJECT/out-three" --judges 3 > /dev/null 2>&1
rc=$?
assert_exit_code 0 "$rc" "three valid judgings exit 0"
assert_exit_code 3 "$(calls three)" "three judgings mean three CLI calls"
if python - "$PROJECT/out-three/verdict.json" <<'EOF'
import json, sys
v = json.load(open(sys.argv[1], encoding="utf-8"))
assert v["outcome"] == "scored", v["outcome"]
assert v["criteria"][0]["score"] == 3, v["criteria"][0]   # 2/5/3 -> 3
assert v["criteria"][2]["score"] == 4, v["criteria"][2]   # 3/4/5 -> 4
assert v["overall"] == 4.0, v["overall"]                  # 3.4/4.2/4.0 -> 4.0
EOF
then
    _pass "medians land per criterion and overall"
else
    _fail "medians land per criterion and overall"
fi

echo "Non-string red flags are rejected, not crashed on"
# A verdict whose red_flags holds objects used to pass validation and then
# blow up (unhashably) inside multi-judge aggregation — a silent exit-0 path.
python - "$PROJECT" <<'EOF'
import json, pathlib, sys
proj = pathlib.Path(sys.argv[1])
names = ["selection_suitability", "balance_and_coverage",
         "ordering_and_structure", "persona_fit", "red_flags"]
v = {"criteria": [{"name": n, "evidence": "e", "reasoning": "r", "score": 2}
                  for n in names],
     "red_flags": [{"flag": "not a string"}], "overall": 2,
     "summary": "flags as objects"}
(proj / "badflags-envelope.json").write_text(
    json.dumps({"result": json.dumps(v)}), encoding="utf-8")
EOF
cat > "$PROJECT/badflags" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/badflags-calls.log"
cat "$PROJECT/badflags-envelope.json"
EOF
chmod +x "$PROJECT/badflags"
judge badflags "$PROJECT/out-badflags" --judges 2 > /dev/null 2>&1
rc=$?
assert_exit_code 1 "$rc" "object red flags exit 1, not a crash-to-scored"
assert_file_contains "$PROJECT/out-badflags/verdict.json" \
    '"outcome": "indeterminate"' "and the verdict is indeterminate"
echo ""

echo "Non-UTF-8 bytes are rejected, not crashed on"
# A response that isn't valid UTF-8 at all used to raise UnicodeDecodeError
# straight through validate()'s bare OSError catch, killing the process
# before any verdict.json was written.
cat > "$PROJECT/badutf8" <<EOF
#!/usr/bin/env bash
echo call >> "$PROJECT/badutf8-calls.log"
printf '\xff\xfe not valid utf-8'
EOF
chmod +x "$PROJECT/badutf8"
judge badutf8 "$PROJECT/out-badutf8" > /dev/null 2>&1
rc=$?
assert_exit_code 1 "$rc" "invalid UTF-8 bytes exit 1, not a crash"
assert_file_contains "$PROJECT/out-badutf8/verdict.json" \
    '"outcome": "indeterminate"' "and the verdict is indeterminate"
echo ""

echo ""
echo "--- run-evals.sh ---"
echo ""

# The runner's overrides exist exactly for this: a fixture dataset dir and a
# temp results dir, so the smoke test touches nothing real and costs nothing.
FIXDS="$PROJECT/fixture-ds"
mkdir -p "$FIXDS/data"
cp "$REPO_ROOT/skills/generation/scripts/generate.fixture.json" \
   "$FIXDS/data/exercises.json"

echo "Smoke: one persona, fixture dataset, fake judge"
CLAUDE_BIN="$PROJECT/ok" bash "$RUNNER" --persona mira \
    --dataset-dir "$FIXDS" --results-dir "$PROJECT/results" > /dev/null 2>&1
rc=$?
assert_exit_code 0 "$rc" "the smoke run exits 0"
run_dir=$(ls -d "$PROJECT/results"/*/ 2>/dev/null | head -1)
for f in mira/plan.json mira/plan.md mira/verdict.json report.md; do
    if [ -f "$run_dir/$f" ]; then
        _pass "$f landed in the run folder"
    else
        _fail "$f landed in the run folder"
    fi
done
assert_file_contains "$run_dir/report.md" "mira" \
    "the report names the persona"
assert_file_contains "$run_dir/report.md" "a fine plan overall" \
    "the report carries the judge's summary"
assert_file_contains "$run_dir/report.md" "Weakest criterion" \
    "the report ends with the weakest-criterion line"
echo ""

echo "--skip-judge needs no CLI at all"
CLAUDE_BIN="$PROJECT/no-such-cli" bash "$RUNNER" --persona mira --skip-judge \
    --dataset-dir "$FIXDS" --results-dir "$PROJECT/results-nojudge" > /dev/null 2>&1
rc=$?
assert_exit_code 0 "$rc" "generate-only exits 0 with a broken CLAUDE_BIN"
run_dir=$(ls -d "$PROJECT/results-nojudge"/*/ 2>/dev/null | head -1)
if [ -f "$run_dir/mira/plan.md" ] && [ ! -f "$run_dir/mira/verdict.json" ]; then
    _pass "a plan lands and no verdict is attempted"
else
    _fail "a plan lands and no verdict is attempted"
fi
assert_file_contains "$run_dir/report.md" "generated" \
    "the report shows the not-judged status"
echo ""

echo "An indeterminate judging fails the run, and the report says so"
CLAUDE_BIN="$PROJECT/garbage" bash "$RUNNER" --persona mira \
    --dataset-dir "$FIXDS" --results-dir "$PROJECT/results-indet" > /dev/null 2>&1
rc=$?
assert_exit_code 1 "$rc" "indeterminate is an infra failure: exit 1"
run_dir=$(ls -d "$PROJECT/results-indet"/*/ 2>/dev/null | head -1)
assert_file_contains "$run_dir/report.md" "| indeterminate |" \
    "the table row shows the status in place of scores"
assert_file_contains "$run_dir/report.md" "## Indeterminate" \
    "the report carries the reason section"
echo ""

echo "A missing dataset dir fails preflight, helpfully"
output=$(bash "$RUNNER" --skip-judge --dataset-dir "$PROJECT/no-dataset-here" \
    --results-dir "$PROJECT/results-nods" 2>&1)
rc=$?
assert_exit_code 2 "$rc" "preflight failure is non-zero"
assert_contains "$output" "git clone" \
    "and the message hands over the exact clone command"

finish_tests
