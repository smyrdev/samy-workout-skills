#!/usr/bin/env bash
# run-evals.sh — the eval pipeline: generate a plan per persona, judge each
# against the rubric, compose one comparison report.
#
#   bash evals/run-evals.sh                     all personas
#   bash evals/run-evals.sh --persona mira      one persona
#   bash evals/run-evals.sh --skip-judge        generate only, no CLI needed
#   bash evals/run-evals.sh --judges 3          median-of-3 judging
#
# --dataset-dir and --results-dir exist so the smoke test can point everything
# at temp dirs; the defaults are the documented layout.
#
# The exit code reflects infrastructure only: preflight failure or any
# indeterminate judging is non-zero. A generation refusal is a FINDING — its
# stderr lands in the report — and findings never fail the run.

set -uo pipefail
export PYTHONIOENCODING=utf-8

EVALS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$EVALS_DIR/.." && pwd)"

DATASET_DIR="$REPO_ROOT/datasets/exercises-dataset"
RESULTS_DIR="$EVALS_DIR/results"
PERSONA=""
SKIP_JUDGE=""
JUDGES=1
TIMEOUT=120

usage() {
    echo "usage: run-evals.sh [--persona NAME] [--skip-judge] [--judges N]" \
         "[--timeout N] [--dataset-dir DIR] [--results-dir DIR]" >&2
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --persona)     PERSONA="${2:?--persona needs a name}";        shift 2 ;;
        --skip-judge)  SKIP_JUDGE=yes;                                shift ;;
        --judges)      JUDGES="${2:?--judges needs a value}";         shift 2 ;;
        --timeout)     TIMEOUT="${2:?--timeout needs a value}";       shift 2 ;;
        --dataset-dir) DATASET_DIR="${2:?--dataset-dir needs a dir}"; shift 2 ;;
        --results-dir) RESULTS_DIR="${2:?--results-dir needs a dir}"; shift 2 ;;
        *) usage ;;
    esac
done

# --- preflights -----------------------------------------------------------
if [ ! -d "$DATASET_DIR" ]; then
    echo "run-evals.sh: no dataset at $DATASET_DIR" >&2
    echo "clone it first:" >&2
    echo "  git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset" >&2
    exit 2
fi
CLI="${CLAUDE_BIN:-claude}"
if [ -z "$SKIP_JUDGE" ]; then
    if ! "$CLI" --version > /dev/null 2>&1; then
        echo "run-evals.sh: the judge CLI ('$CLI') did not answer --version." >&2
        echo "The judge runs through the Claude Code CLI — see evals/README.md." >&2
        exit 2
    fi
fi

# --- fresh run folder, never overwritten ----------------------------------
RUN_DATE=$(date +%Y-%m-%d)
BASE="$RESULTS_DIR/$(date +%Y-%m-%d-%H%M)"
RUN_DIR="$BASE"
n=1
while [ -e "$RUN_DIR" ]; do
    n=$((n + 1))
    RUN_DIR="$BASE-$n"
done
mkdir -p "$RUN_DIR"

# --- personas -------------------------------------------------------------
if [ -n "$PERSONA" ]; then
    [ -d "$EVALS_DIR/personas/$PERSONA" ] || {
        echo "run-evals.sh: no persona named '$PERSONA' under evals/personas/" >&2
        exit 2
    }
    PERSONAS=("$PERSONA")
else
    PERSONAS=()
    for d in "$EVALS_DIR/personas"/*/; do
        PERSONAS+=("$(basename "$d")")
    done
fi

# --- generate, then judge -------------------------------------------------
# Outcomes are deliberately left on disk rather than threaded through bash:
# gen-error.txt present = generation-failed, verdict.json's outcome field
# says scored/indeterminate, a plan with neither = generated but not judged.
# The report reads the disk, and so can a human.
INDETERMINATE=0
for p in "${PERSONAS[@]}"; do
    src="$EVALS_DIR/personas/$p"
    pdir="$RUN_DIR/$p"
    mkdir -p "$pdir"

    rules_args=()
    [ -f "$src/rules.json" ] && rules_args=(--rules "$src/rules.json")

    if ! python "$REPO_ROOT/skills/generation/scripts/generate.py" \
            --profile "$src/profile.json" --program "$src/program.json" \
            "${rules_args[@]}" \
            --dataset-dir "$DATASET_DIR" --today "$RUN_DATE" \
            --write "$pdir/plan.json" --write-md "$pdir/plan.md" \
            > /dev/null 2> "$pdir/gen-error.txt"; then
        echo "$p: generation-failed (stderr saved)"
        continue
    fi
    rm -f "$pdir/gen-error.txt"

    if [ -n "$SKIP_JUDGE" ]; then
        echo "$p: generated"
        continue
    fi

    if bash "$EVALS_DIR/judge.sh" "$EVALS_DIR/rubric/plan-quality.md" \
            "$src/persona.yaml" "$pdir/plan.md" "$pdir" \
            --timeout "$TIMEOUT" --judges "$JUDGES" > /dev/null 2>&1; then
        echo "$p: scored"
    else
        echo "$p: indeterminate"
        INDETERMINATE=1
    fi
done

# --- compose report.md from what is on disk -------------------------------
if ! python - "$RUN_DIR" <<'EOF'
import json, os, sys

run_dir = sys.argv[1]
CRITERIA = ["selection_suitability", "balance_and_coverage",
            "ordering_and_structure", "persona_fit", "red_flags"]

rows, summaries, failures, indets = [], [], [], []
for p in sorted(os.listdir(run_dir)):
    pdir = os.path.join(run_dir, p)
    if not os.path.isdir(pdir):
        continue
    gen_error = os.path.join(pdir, "gen-error.txt")
    verdict_file = os.path.join(pdir, "verdict.json")
    if os.path.exists(gen_error):
        rows.append((p, "generation-failed", None))
        failures.append((p, open(gen_error, encoding="utf-8").read().strip()))
    elif os.path.exists(verdict_file):
        v = json.load(open(verdict_file, encoding="utf-8"))
        if v.get("outcome") == "scored":
            scores = {c["name"]: c["score"] for c in v["criteria"]}
            rows.append((p, "scored", (scores, v["overall"], len(v["red_flags"]))))
            summaries.append((p, v["summary"]))
        else:
            rows.append((p, "indeterminate", None))
            indets.append((p, v.get("reason", "no reason recorded")))
    else:
        rows.append((p, "generated", None))

lines = [f"# Eval report — {os.path.basename(run_dir)}", ""]
lines.append("| persona | " + " | ".join(CRITERIA) + " | overall | red flags |")
lines.append("|" + "---|" * (len(CRITERIA) + 3))
for p, status, data in rows:
    if status == "scored":
        scores, overall, red = data
        cells = [str(scores.get(n, "?")) for n in CRITERIA]
        lines.append(f"| {p} | " + " | ".join(cells) + f" | {overall} | {red} |")
    else:
        cells = ["—"] * len(CRITERIA)
        lines.append(f"| {p} | " + " | ".join(cells) + f" | {status} | — |")

if summaries:
    lines += ["", "## Judge summaries", ""]
    for p, s in summaries:
        lines += [f"**{p}** — {s}", ""]

if indets:
    lines += ["", "## Indeterminate", ""]
    for p, reason in indets:
        lines += [f"- {p}: {reason}"]

if failures:
    lines += ["", "## Generation failures", ""]
    for p, err in failures:
        lines += [f"**{p}**", "", "```", err, "```", ""]

scored = [data for _, status, data in rows if status == "scored"]
if scored:
    means = {n: sum(s[n] for s, _, _ in scored) / len(scored) for n in CRITERIA}
    weakest = min(means, key=means.get)
    lines += ["", f"Weakest criterion across the matrix: "
                  f"{weakest} (mean {means[weakest]:.1f})"]

report = os.path.join(run_dir, "report.md")
open(report, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"report: {report}")
EOF
then
    echo "run-evals.sh: report composition failed" >&2
    exit 2
fi

exit "$INDETERMINATE"
