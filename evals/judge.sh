#!/usr/bin/env bash
# judge.sh — rubric + persona.yaml + plan.md -> claude -p -> verdict.json
#
# One judging is one CLI call. The prompt goes in on STDIN FROM A FILE, never
# as an argv parameter: rubric + plan together can blow past Windows' ~32KB
# argv limit. The CLI answers with an envelope — a JSON object whose "result"
# field holds the judge's text — and the verdict JSON is parsed out of that.
#
# Failure ladder per judging: bad output -> one retry -> give up. A timeout is
# not retried (it would just time out again). Either way a verdict.json is
# still written — {"outcome": "indeterminate", ...} — and the exit code is 1,
# so a caller can never mistake infra noise for a quality signal.
#
# The prompt and every raw CLI response are saved next to the verdict: when a
# run goes indeterminate, the postmortem is already on disk.

set -uo pipefail
export PYTHONIOENCODING=utf-8

usage() {
    echo "usage: judge.sh <rubric.md> <persona.yaml> <plan.md> <out-dir>" \
         "[--timeout N] [--judges N]" >&2
    exit 2
}

[ $# -ge 4 ] || usage
RUBRIC="$1"; PERSONA="$2"; PLAN="$3"; OUTDIR="$4"
shift 4

TIMEOUT=120
JUDGES=1
while [ $# -gt 0 ]; do
    case "$1" in
        --timeout) TIMEOUT="${2:?--timeout needs a value}"; shift 2 ;;
        --judges)  JUDGES="${2:?--judges needs a value}";  shift 2 ;;
        *) usage ;;
    esac
done

for f in "$RUBRIC" "$PERSONA" "$PLAN"; do
    [ -f "$f" ] || { echo "judge.sh: missing input: $f" >&2; exit 2; }
done
mkdir -p "$OUTDIR"

CLI="${CLAUDE_BIN:-claude}"
PROMPT="$OUTDIR/prompt.txt"

# --- build the one prompt -------------------------------------------------
# Fixed instructions + the exact verdict shape + rubric + persona + plan.
# Instructions ask for evidence and reasoning BEFORE each score, the exact
# criterion names in the exact order, and make the judge compute overall and
# apply the red-flag cap itself — this script validates, never recomputes.
python - "$RUBRIC" "$PERSONA" "$PLAN" "$PROMPT" <<'EOF'
import sys

rubric, persona, plan, out = sys.argv[1:5]
read = lambda p: open(p, encoding="utf-8").read()

shape = """{
  "criteria": [
    {"name": "selection_suitability", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "balance_and_coverage", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "ordering_and_structure", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "persona_fit", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "red_flags", "evidence": "...", "reasoning": "...", "score": 5}
  ],
  "red_flags": [],
  "overall": 4.2,
  "summary": "one paragraph for the report table"
}"""

prompt = "\n".join([
    "You are an impartial judge scoring one generated training plan for one",
    "persona, using the rubric below. Use no tools. Respond with pure JSON",
    "only — no prose before or after it, no markdown fences.",
    "",
    "The JSON must have exactly this shape:",
    shape,
    "",
    "Rules:",
    "- Score the five criteria in exactly this order, with exactly these",
    "  names: selection_suitability, balance_and_coverage,",
    "  ordering_and_structure, persona_fit, red_flags.",
    "- For each criterion, write the evidence (citing specific exercises and",
    "  days from the plan) and your reasoning BEFORE choosing the score.",
    "  Scores are integers from 1 to 5.",
    "- red_flags is a list of short strings, one per red flag; empty if none.",
    "- Compute overall yourself. If red_flags is non-empty, overall must not",
    "  exceed 2.",
    "- summary is one paragraph a report table can quote.",
    "",
    "=== RUBRIC ===",
    read(rubric),
    "=== PERSONA ===",
    read(persona),
    "=== PLAN ===",
    read(plan),
])
open(out, "w", encoding="utf-8").write(prompt)
EOF

# --- the envelope parser / verdict validator ------------------------------
# Written to a temp file once so both attempts (and every judging) reuse it.
# Prints the normalized verdict on stdout when valid; exits 1 with the reason
# on stderr otherwise. Tolerates the model wrapping its JSON in ``` fences.
VALIDATE_PY=$(mktemp)
trap 'rm -f "$VALIDATE_PY"' EXIT
cat > "$VALIDATE_PY" <<'EOF'
import json, re, sys

NAMES = ["selection_suitability", "balance_and_coverage",
         "ordering_and_structure", "persona_fit", "red_flags"]

def fail(reason):
    print(reason, file=sys.stderr)
    sys.exit(1)

try:
    raw = open(sys.argv[1], encoding="utf-8").read()
except OSError as e:
    fail(f"cannot read response: {e}")

try:
    envelope = json.loads(raw)
except json.JSONDecodeError:
    fail("CLI output is not a JSON envelope")
if not isinstance(envelope, dict) or not isinstance(envelope.get("result"), str):
    fail("envelope has no string 'result' field")

text = envelope["result"].strip()
text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
text = re.sub(r"\s*```$", "", text)
try:
    v = json.loads(text)
except json.JSONDecodeError:
    fail("the judge's text is not JSON")

crits = v.get("criteria")
if not isinstance(crits, list) or len(crits) != len(NAMES):
    fail(f"expected {len(NAMES)} criteria")
for crit, expected in zip(crits, NAMES):
    if not isinstance(crit, dict) or crit.get("name") != expected:
        fail(f"criterion out of place: expected '{expected}'")
    score = crit.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
        fail(f"{expected}: score must be an integer 1-5")
    for key in ("evidence", "reasoning"):
        if not isinstance(crit.get(key), str) or not crit[key].strip():
            fail(f"{expected}: empty {key}")

if not isinstance(v.get("red_flags"), list):
    fail("red_flags must be a list")
overall = v.get("overall")
if not isinstance(overall, (int, float)) or isinstance(overall, bool):
    fail("overall must be a number")
if v["red_flags"] and overall > 2:
    fail("red flags present but the cap on overall was not applied")
if not isinstance(v.get("summary"), str) or not v["summary"].strip():
    fail("empty summary")

print(json.dumps(v))
EOF

write_indeterminate() {
    python - "$OUTDIR/verdict.json" "$1" <<'EOF'
import json, sys
json.dump({"outcome": "indeterminate", "reason": sys.argv[2]},
          open(sys.argv[1], "w", encoding="utf-8"), indent=2)
EOF
}

# --- judge ----------------------------------------------------------------
for j in $(seq 1 "$JUDGES"); do
    valid=""
    reason=""
    for attempt in 1 2; do
        RAW="$OUTDIR/response-j${j}-a${attempt}.json"
        # -k makes the deadline real: the CLI ignores SIGTERM, and a plain
        # `timeout` would report 124 while waiting for it anyway.
        timeout -k 10 "$TIMEOUT" "$CLI" -p --output-format json \
            < "$PROMPT" > "$RAW" 2>&1
        rc=$?
        if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
            write_indeterminate "judging $j timed out after ${TIMEOUT}s"
            exit 1
        fi
        if parsed=$(python "$VALIDATE_PY" "$RAW" 2>"$OUTDIR/invalid-reason.txt"); then
            printf '%s\n' "$parsed" > "$OUTDIR/judge-$j.json"
            valid=yes
            break
        fi
        reason=$(cat "$OUTDIR/invalid-reason.txt" 2>/dev/null)
    done
    if [ -z "$valid" ]; then
        write_indeterminate "judging $j produced an invalid verdict twice: ${reason:-unknown}"
        exit 1
    fi
done

# --- write the final verdict ----------------------------------------------
# One judging passes through as-is; several aggregate: per-criterion median,
# median overall, union of red flags — and the cap re-applied to the median,
# since a red flag any judge saw must still cap the aggregate.
python - "$OUTDIR/verdict.json" "$JUDGES" "$OUTDIR" <<'EOF'
import json, statistics, sys

out, judges, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
verdicts = [json.load(open(f"{outdir}/judge-{j}.json", encoding="utf-8"))
            for j in range(1, judges + 1)]

if judges == 1:
    final = {"outcome": "scored", **verdicts[0]}
else:
    names = [c["name"] for c in verdicts[0]["criteria"]]
    criteria = [{"name": name,
                 "score": statistics.median([v["criteria"][i]["score"]
                                             for v in verdicts])}
                for i, name in enumerate(names)]
    red_flags = sorted({flag for v in verdicts for flag in v["red_flags"]})
    overall = statistics.median([v["overall"] for v in verdicts])
    if red_flags and overall > 2:
        overall = 2
    final = {"outcome": "scored", "judges": judges, "criteria": criteria,
             "red_flags": red_flags, "overall": overall,
             "summary": verdicts[0]["summary"],
             "summaries": [v["summary"] for v in verdicts]}

json.dump(final, open(out, "w", encoding="utf-8"), indent=2)
EOF
exit 0
