# Quality Evals — Reference Implementation Plan (Claude's copy)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Learning-mode note:** Samy implements from his own copy
> (`2026-08-12-quality-evals-for-samy.md`). This file is the review baseline:
> when his code lands, review it against the contracts and code below —
> differences are discussion points, not automatic defects.

**Goal:** An offline-testable pipeline that generates plans for 7 checked-in personas, scores each with a `claude -p` LLM judge against a written rubric, and composes a comparison report — one command per config tweak.

**Architecture:** `evals/` is a pure consumer of the two skills. `generate.py` produces the artifact deterministically (`--today` pinned); the only LLM is the judge. Three-valued per-persona outcome (`scored` / `generation-failed` / `indeterminate`); scores never gate; exit codes reflect infrastructure only.

**Tech Stack:** bash (`set -uo pipefail`, `tests/skills` conventions), python stdlib for all JSON (no jq), Claude Code CLI for judging only, fake-CLI (`CLAUDE_BIN`) offline tests.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-12-quality-evals-design.md`.
- `evals/` never writes under `profile/`; never edits `skills/`; owns no tuning numbers.
- `evals/results/` gitignored; dated run folders never overwritten.
- Folder not vendor-named; the Claude Code CLI requirement documented in `evals/README.md` and enforced by a runner preflight.
- The runner validates verdict shape but never recomputes scores; the judge computes `overall` and applies the red-flag cap.
- Prompts to the CLI travel via stdin from a file, never argv (Windows ~32KB argv limit).
- Every python call that may print emoji sets `PYTHONIOENCODING=utf-8`; every CLI call runs under `timeout -k 10`.
- **Spec deviation (documented):** the 2-day edge persona is impossible — `program.schema.json` requires `days_per_week >= 3` and `volume.py` accepts `--days 3..7`. The awkward persona is 3-day / tier-1 / `20-40` instead; the days axis is 3–6.

Canonical criterion names, used identically in the rubric, judge prompt, validation, fakes, and report:

```
selection_suitability, balance_and_coverage, ordering_and_structure, persona_fit, red_flags
```

Verdict file contract (consumed by the runner's report step):

```json
{
  "outcome": "scored",
  "criteria": [{"name": "selection_suitability", "evidence": "…", "reasoning": "…", "score": 4}, "… 5 entries, fixed order"],
  "red_flags": [],
  "overall": 4.2,
  "summary": "one paragraph",
  "judges": 3
}
```
`judges` present only when `--judges N > 1`. Indeterminate verdicts are
`{"outcome": "indeterminate", "reason": "…"}`. `generation-failed` has no
verdict file — `gen-error.txt` holds the generator's stderr.

---

### Task 1: Scaffold — README and gitignore

**Files:**
- Create: `evals/README.md`
- Modify: `.gitignore` (append at end)

**Interfaces:**
- Produces: the `evals/` directory layout every later task writes into; the documented CLI requirement Task 5's preflight enforces.

- [ ] **Step 1: Append to `.gitignore`**

```gitignore
# Eval runs are throwaway output, regenerated on demand — like datasets/.
evals/results/
```

- [ ] **Step 2: Write `evals/README.md`**

```markdown
# Plan-quality evals

Generates a workout plan for each checked-in persona, has an LLM judge score
it against `rubric/plan-quality.md`, and composes a comparison report — so a
tweak to `volume.config.json`, `generate.config.json` or `datasets.json` can
be evaluated across the whole matrix in one command.

Scores are for eyes, not exit codes: the runner's exit status reflects
infrastructure only, and nothing here gates CI.

## Requirements

- python 3 and bash (the same pair `tests/skills` needs)
- the exercise dataset, cloned locally:

      git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset

- the [Claude Code CLI](https://code.claude.com), logged in — judging only.
  `--skip-judge` runs the generation half without it. This is the one
  vendor-specific dependency; swapping the judge means editing `judge.sh`
  only.

## Running

    bash evals/run-evals.sh                     # all personas: generate + judge + report
    bash evals/run-evals.sh --persona <name>    # one persona
    bash evals/run-evals.sh --skip-judge        # generate only — free; for diffing plans
    bash evals/run-evals.sh --judges 3          # median-of-3 judging

Each run writes a fresh `results/<YYYY-MM-DD-HHMM>/` folder: per persona
`plan.json`, `plan.md` and `verdict.json`, then `report.md` at the top.
Results are gitignored and never overwritten.

## Outcomes

- `scored` — the generator ran and the judge returned a valid verdict.
- `generation-failed` — `generate.py` refused. A real finding: the report
  shows its stderr verbatim, and the message names the file to fix.
- `indeterminate` — the judge timed out or emitted garbage twice. Infra
  noise; reported, never scored.

## The tuning loop

Tweak a config → `--skip-judge` → diff the new run's plan files against the
last run's (only the date line differs on a no-op) → judge only when the
diff looks interesting. Judged scores are comparable within a run and
between runs in the same sitting; the CLI's model can drift over long
spans, so don't compare scores across months.

## Adding a persona

Copy an existing folder under `personas/`, edit `profile.json` and the
`program` block of `program.json`, rewrite `persona.yaml`, then refill the
volume block (the one number-owner is volume.py):

    python skills/onboarding/scripts/volume.py \
        --profile evals/personas/<slug>/profile.json \
        --today <today> --write evals/personas/<slug>/program.json

`generate.py`'s strict refusals are the validation — if the runner's
generation step exits 0, the persona is well-formed.
```

- [ ] **Step 3: Verify ignore behaviour**

Run: `mkdir -p evals/results && touch evals/results/x && git status --short`
Expected: no `evals/results/` in the output. Then `rm evals/results/x`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore evals/README.md
git commit -m "evals: scaffold README and results gitignore"
```

---

### Task 2: The rubric

**Files:**
- Create: `evals/rubric/plan-quality.md`

**Interfaces:**
- Produces: the five criterion names (must match the canonical list above) — Task 4's prompt embeds this file verbatim and validates against those names.

- [ ] **Step 1: Write `evals/rubric/plan-quality.md`**

```markdown
# Plan quality rubric

You are judging one generated training plan for one person. Score each of
the five criteria below from 1 to 5 against its anchors. For every
criterion, cite specific exercises, days or table rows as evidence first,
reason second, and only then score. Judge only what is in front of you.

Out of scope — checked deterministically elsewhere, do not score them here:
schema validity, whether volume targets add up, whether an exercise exists
in the dataset, file-overwrite behaviour.

## 1. selection_suitability

Do the chosen exercises fit this person's experience level and equipment?
Are training slots spent well?

- **5** — every exercise is appropriate for the stated experience and
  available equipment; no two near-duplicate variations of the same movement
  eating separate slots in the same week without a reason.
- **3** — mostly sensible; one or two odd picks (too advanced, too trivial,
  or awkward for the equipment) or one redundant variation pair.
- **1** — several exercises this person cannot or should not be doing, or
  slots repeatedly wasted on near-identical movements.

## 2. balance_and_coverage

Look at the week as a whole. Is pushing balanced against pulling, hinging
against squatting? Does any muscle get hammered on back-to-back days in a
way the split's intent argues against?

- **5** — the week reads balanced; hard work for a muscle group is spaced;
  nothing is conspicuously over- or under-represented relative to the
  plan's own volume table.
- **3** — broadly balanced with one visible wrinkle (e.g. two heavy pressing
  days adjacent, one group's work bunched into one day).
- **1** — clearly lopsided week: a movement pattern dominates, or a muscle
  is trained hard on consecutive days for no stated reason.

## 3. ordering_and_structure

Within each session: compounds before isolation, big demanding lifts early,
trailer work (core, calves) last, and a total workload that plausibly fits
the profile's session minutes.

- **5** — every session flows: heavy compounds → secondary work →
  isolation/trailers, and the exercise count × sets is realistic for the
  stated session length.
- **3** — order is mostly right with an isolated inversion, or one session
  looks tight for the time box.
- **1** — isolation before main compounds, trailers mid-session, or
  sessions that obviously cannot fit the stated minutes.

## 4. persona_fit

Read the person's story, goals, constraints and preferences. Is the plan a
plan for *this* person? Are their written rules (exclusions, focus,
must-includes) visibly respected in the output?

- **5** — the plan honors the narrative in spirit (goal emphasis visible,
  constraints steered around) and every personal rule is reflected.
- **3** — rules are respected but the narrative barely shows: a generic —
  if competent — plan for someone with these stats.
- **1** — the plan contradicts the narrative (e.g. loads an area the story
  flags as fragile) or ignores a written rule.

## 5. red_flags

Anything a coach would veto outright: unsafe for the stated level, a
movement clearly contraindicated by the person's story, absurd volume for a
beginner, a week that invites injury.

- **5** — nothing a coach would veto.
- **3** — one questionable call worth a conversation, not a veto.
- **1** — at least one outright veto.

List every veto-level item in the `red_flags` array of your verdict. Any
red flag caps the overall score at 2, and you apply that cap yourself.
```

- [ ] **Step 2: Verify criterion names match the canonical list**

Run: `grep -o '^## [0-9]\. .*' evals/rubric/plan-quality.md`
Expected: the five names in order, exactly as in Global Constraints.

- [ ] **Step 3: Commit**

```bash
git add evals/rubric/plan-quality.md
git commit -m "evals: plan-quality rubric with anchored criteria"
```

---

### Task 3: The persona matrix

**Files:**
- Create: `evals/personas/<slug>/{persona.yaml,profile.json,program.json}` for 7 slugs; `evals/personas/ruleful-rita/rules.json`

**Interfaces:**
- Consumes: `skills/onboarding/examples/profile.example.json` (copy base), `volume.py --profile … --today 2026-08-12 --write …` (fills each `program.json` volume block in place).
- Produces: the persona folders Task 5 iterates over; slug `beginner-liam` is hard-referenced by Task 6's smoke test.

- [ ] **Step 1: Create the seven personas**

Every `profile.json` starts as a copy of the example with
`created_at`/`updated_at` set to `2026-08-12T00:00:00Z`, then applies the
row below. Every `program.json` is hand-written as
`{"$schema_version": "1.0", "created_at": "2026-08-12T00:00:00Z", "program": {…}}`
with the row's program values, then volume-filled by the command in Step 2.
`cardio` is `beginner` and `gym.notes` is `null` unless stated.

| slug | name/sex/dob | h/w/bf% | lifting | gym | benchmarks true | program |
|---|---|---|---|---|---|---|
| `beginner-liam` | Liam, male, 2002-03-10 | 181cm / 74kg / 18-23 | beginner | commercial_gym | pushups_15 | "First Foundations" 🌱, hypertrophy, 3d, 40-60, full_body, deload false |
| `tight-tara` | Tara, female, 1991-07-22 | 167cm / 63kg / 24-29 | intermediate | local_gym | pushups_15, bench_press_10 | "Lunch Hour Lifts" ⏱️, both, 4d, 20-40, upper_lower, deload false |
| `advanced-ava` | Ava, female, 1996-01-05 | 172cm / 70kg / 13-17 | advanced | everything_gym | all seven | "Peak Season" 🏆, hypertrophy, 6d, 90-120, upper_lower, deload true |
| `home-hakim` | Hakim, male, 1988-11-30 | 176cm / 85kg / 18-23 | intermediate | garage_gym, notes: "barbell, dumbbells to 30 kg, bands, pull-up bar — no machines" | pullups_5, dips_10, pushups_15, bench_press_10, incline_press_10 | "Garage Winter" 🏠, hypertrophy, 4d, 60-90, full_body, deload true |
| `strength-sana` | Sana, female, 1993-05-17 | 169cm / 68kg / 24-29 | intermediate (cardio intermediate) | warehouse_gym | pushups_15, bench_press_10 | "Barbell Base" 🏋️, strength, 4d, 60-90, upper_lower, deload true |
| `ruleful-rita` | Rita, female, 1985-09-09 | 164cm / 60kg / 13-17 | advanced | commercial_gym | all but overhead_press_10 | "Delt Focus Block" 💥, hypertrophy, 5d, 60-90, upper_lower, deload true |
| `edge-erik` | Erik, male, 1979-02-14 | 183cm / 95kg / 30-34 | beginner (cardio none) | garage_gym, notes: "a pair of adjustable dumbbells and one long band — nothing else" | none | "Something Beats Nothing" 🌒, both, 3d, 20-40, full_body, deload false |

Axes covered: experience beginner/intermediate/advanced; commercial vs home;
days 3/4/5/6; all three goals; sessions 20-40 → 90-120; both splits; one
meaty rules.json (rita); one awkward edge (erik — shortfall country).

`persona.yaml` shape (all seven; `interview_answers: {}` is the phase-2
hook and stays empty):

```yaml
name: Ruleful Rita
one_liner: advanced lifter chasing capped delts; her knees veto heavy squats
story: |
  Rita has trained for fifteen years and knows exactly what she responds
  to. Years of heavy squatting left her knees cranky, so she has moved her
  leg work to hinges, lunges and machines and does not want barbell squats
  programmed. She also refuses smith-machine work — she finds the fixed
  path aggravates the same knees.
goal_detail: |
  Bring up side and rear delts this block; keep bench pressing heavy.
constraints:
  - no barbell squats (knees)
  - no smith machine
preferences:
  - shoulders first when possible
  - barbell bench press must stay in the program
interview_answers: {}
```

Each of the other six carries at least one injury or goal detail in the same
shape. The load-bearing ones:

- `beginner-liam` — left knee grumbles on deep leg work (physio-cleared);
  wants visible arm and chest progress. First real year of training.
- `tight-tara` — 35-minute lunch-break sessions, hard stop; wants strength
  without soreness wrecking her running; prefers free weights over waiting
  for machines.
- `advanced-ava` — physique-show prep next spring; side delts and upper
  back are the visible weak points; loves cables and machines.
- `home-hakim` — an old shoulder impingement flares on overhead barbell
  pressing; trains alone in the garage. **Deliberately narrative-only** (no
  rules.json): the generator cannot see it, the judge can — this persona
  exists to make `persona_fit` surface the missing injury feature.
- `strength-sana` — wants her first powerlifting meet next year; the
  barbell lifts are the point, everything else supports them.
- `edge-erik` — desk job, restarting at 47 after a decade off; can spare
  three short evenings; owns almost nothing. Shortfall warnings expected —
  the judge should see the plan being honest about them.

`ruleful-rita/rules.json` (shape mirrors `rules.example.json`):

```json
{
  "$schema_version": "1.0",
  "exclude": {
    "exercises": ["barbell squat", "burpee"],
    "equipment": ["smith machine"],
    "movement_groups": [],
    "muscles": []
  },
  "focus": {
    "muscles": ["shoulders"],
    "must_include": ["barbell bench press"]
  }
}
```

- [ ] **Step 2: Fill every volume block**

Run for each slug (pinned date keeps the checked-in file stable):

```bash
python skills/onboarding/scripts/volume.py \
    --profile evals/personas/<slug>/profile.json \
    --today 2026-08-12 --write evals/personas/<slug>/program.json
```

Expected: each program.json gains a complete `volume` block; edge-erik's may
carry warnings — that is the point of him.

- [ ] **Step 3: Verify all seven generate, offline**

```bash
TMP=$(mktemp -d) && mkdir -p "$TMP/data"
cp skills/generation/scripts/generate.fixture.json "$TMP/data/exercises.json"
for p in evals/personas/*/; do
  rules=""; [ -f "$p/rules.json" ] && rules="--rules $p/rules.json"
  PYTHONIOENCODING=utf-8 python skills/generation/scripts/generate.py \
      --profile "$p/profile.json" --program "$p/program.json" \
      --dataset-dir "$TMP" --today 2026-08-12 $rules > /dev/null \
      && echo "OK $p" || echo "REFUSED $p"
done
```

Expected: seven `OK` lines. (`short:` warnings inside a plan are fine;
exit-3 refusals are not.)

- [ ] **Step 4: Commit**

```bash
git add evals/personas
git commit -m "evals: seven-persona matrix with narratives and volume blocks"
```

---

### Task 4: judge.sh, test-driven

**Files:**
- Create: `evals/judge.sh`
- Test: `tests/skills/test-eval-harness.sh` (runner smoke tests join it in Task 5)

**Interfaces:**
- Consumes: rubric (Task 2), a persona.yaml and a plan.md; `CLAUDE_BIN` env override (same convention as `tests/skills/test-helpers.sh`).
- Produces: `bash evals/judge.sh --rubric F --persona F --plan F --out F [--timeout N] [--judges N]` → exit 0 with a `scored` verdict at `--out`, exit 1 with an `indeterminate` verdict, exit 2 on usage error. Side artifacts next to `--out`: `judge-prompt.txt`, `judge-<i>-attempt-<k>.json` (raw CLI output), `judge-<i>-verdict.json` (parsed per-judging).

- [ ] **Step 1: Write the failing tests** — `tests/skills/test-eval-harness.sh`:

```bash
#!/usr/bin/env bash
# The eval pipeline's own plumbing, offline: judge.sh's verdict handling
# under fake CLIs, and (from Task 5) one runner smoke test on the bundled
# fixture dataset. Plan *quality* is never asserted here — that is the
# judge's job, and it costs tokens.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

JUDGE="$REPO_ROOT/evals/judge.sh"
RUNNER="$REPO_ROOT/evals/run-evals.sh"
FIXTURE="$REPO_ROOT/skills/generation/scripts/generate.fixture.json"

PROJECT=$(create_test_project)
trap 'cleanup_test_project "$PROJECT"' EXIT

# Plumbing inputs — content is irrelevant to what these tests pin.
printf 'rubric text\n' > "$PROJECT/rubric.md"
printf 'name: Test Person\n' > "$PROJECT/persona.yaml"
printf '# plan\n' > "$PROJECT/plan.md"

run_judge() {
    out=$(CLAUDE_BIN="$1" bash "$JUDGE" --rubric "$PROJECT/rubric.md" \
        --persona "$PROJECT/persona.yaml" --plan "$PROJECT/plan.md" "${@:2}" 2>&1)
    code=$?
}

# Fake CLIs. Each logs its invocation so retry counts are assertable, and
# emits the --output-format json envelope the real CLI produces: a JSON
# object whose "result" field holds the judge's text.
cat > "$PROJECT/good-judge" <<EOF
#!/usr/bin/env bash
echo run >> "$PROJECT/calls.log"
python "$PROJECT/emit-verdict.py" 4
EOF
cat > "$PROJECT/emit-verdict.py" <<'EOF'
import json, sys
score = int(sys.argv[1])
names = ["selection_suitability", "balance_and_coverage",
         "ordering_and_structure", "persona_fit", "red_flags"]
verdict = {
    "criteria": [{"name": n, "evidence": "e", "reasoning": "r", "score": score}
                 for n in names],
    "red_flags": [],
    "overall": float(score),
    "summary": "FIXTURE-SUMMARY: a solid week.",
}
print(json.dumps({"type": "result", "result": json.dumps(verdict)}))
EOF
cat > "$PROJECT/garbage-judge" <<EOF
#!/usr/bin/env bash
echo run >> "$PROJECT/calls.log"
echo '{"type": "result", "result": "I think the plan is nice."}'
EOF
# Garbage on the first call, valid on the second — the retry must recover.
cat > "$PROJECT/flaky-judge" <<EOF
#!/usr/bin/env bash
echo run >> "$PROJECT/calls.log"
if [ -f "$PROJECT/flaky.state" ]; then
    python "$PROJECT/emit-verdict.py" 3
else
    touch "$PROJECT/flaky.state"
    echo 'not even an envelope'
fi
EOF
# Scores 2, 5, 3 across three calls — the median must land on 3.
cat > "$PROJECT/varying-judge" <<EOF
#!/usr/bin/env bash
echo run >> "$PROJECT/varying.log"
n=\$(wc -l < "$PROJECT/varying.log")
case "\$n" in
    1) python "$PROJECT/emit-verdict.py" 2 ;;
    2) python "$PROJECT/emit-verdict.py" 5 ;;
    *) python "$PROJECT/emit-verdict.py" 3 ;;
esac
EOF
cat > "$PROJECT/slow-judge" <<'EOF'
#!/usr/bin/env bash
sleep 30
EOF
chmod +x "$PROJECT"/good-judge "$PROJECT"/garbage-judge \
    "$PROJECT"/flaky-judge "$PROJECT"/varying-judge "$PROJECT"/slow-judge

echo "=== Eval Harness ==="
echo ""

echo "judge.sh: a valid verdict is scored"
rm -f "$PROJECT/calls.log"
run_judge "$PROJECT/good-judge" --out "$PROJECT/v-good.json"
assert_exit_code 0 "$code" "a valid verdict exits 0"
assert_file_contains "$PROJECT/v-good.json" '"outcome": "scored"' "verdict is marked scored"
assert_file_contains "$PROJECT/v-good.json" '"selection_suitability"' "criteria carried through"
assert_file_contains "$PROJECT/v-good.json" 'FIXTURE-SUMMARY' "summary carried through"
[ "$(wc -l < "$PROJECT/calls.log")" -eq 1 ] \
    && _pass "a clean run calls the CLI once" \
    || _fail "a clean run calls the CLI once"
echo ""

echo "judge.sh: garbage gets one retry, then indeterminate"
rm -f "$PROJECT/calls.log"
run_judge "$PROJECT/garbage-judge" --out "$PROJECT/v-garbage.json"
assert_exit_code 1 "$code" "garbage twice exits 1"
assert_file_contains "$PROJECT/v-garbage.json" '"outcome": "indeterminate"' \
    "the verdict says indeterminate, never a fake score"
[ "$(wc -l < "$PROJECT/calls.log")" -eq 2 ] \
    && _pass "exactly one retry happened" \
    || _fail "exactly one retry happened (calls: $(wc -l < "$PROJECT/calls.log"))"
echo ""

echo "judge.sh: the retry recovers a flaky judge"
rm -f "$PROJECT/calls.log" "$PROJECT/flaky.state"
run_judge "$PROJECT/flaky-judge" --out "$PROJECT/v-flaky.json"
assert_exit_code 0 "$code" "garbage-then-valid exits 0"
assert_file_contains "$PROJECT/v-flaky.json" '"outcome": "scored"' "the second attempt scored"
echo ""

echo "judge.sh: a timeout is indeterminate, and enforced"
start=$(date +%s)
run_judge "$PROJECT/slow-judge" --out "$PROJECT/v-slow.json" --timeout 2
elapsed=$(( $(date +%s) - start ))
assert_exit_code 1 "$code" "a timed-out judge exits 1"
assert_file_contains "$PROJECT/v-slow.json" '"outcome": "indeterminate"' "timeout is indeterminate"
assert_file_contains "$PROJECT/v-slow.json" 'timed out' "the reason names the timeout"
[ "$elapsed" -lt 20 ] \
    && _pass "the deadline was enforced (${elapsed}s)" \
    || _fail "the deadline was enforced (took ${elapsed}s)"
echo ""

echo "judge.sh: --judges 3 takes the per-criterion median"
rm -f "$PROJECT/varying.log"
run_judge "$PROJECT/varying-judge" --out "$PROJECT/v-median.json" --judges 3
assert_exit_code 0 "$code" "three judgings exit 0"
assert_file_contains "$PROJECT/v-median.json" '"judges": 3' "the verdict records the judge count"
assert_file_contains "$PROJECT/v-median.json" '"overall": 3' "overall is the median of 2, 5, 3"
echo ""

echo "judge.sh: usage errors exit 2"
out=$(bash "$JUDGE" --rubric "$PROJECT/rubric.md" 2>&1); code=$?
assert_exit_code 2 "$code" "missing flags are a usage error"
assert_contains "$out" "required" "the message names what is missing"

finish_tests
```

- [ ] **Step 2: Run to verify failure**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: FAIL — `evals/judge.sh` does not exist yet.

- [ ] **Step 3: Write `evals/judge.sh`**

```bash
#!/usr/bin/env bash
# Judge one generated plan against the rubric — one persona per call, so a
# judging is never contaminated by cross-comparison in a single prompt.
#
# Usage:
#   judge.sh --rubric FILE --persona FILE --plan FILE --out VERDICT.json
#            [--timeout SECONDS] [--judges N]
#
# CLAUDE_BIN overrides the CLI — the offline tests judge with fakes.
# Exit 0: verdict written, outcome "scored".
# Exit 1: verdict written, outcome "indeterminate" (timeout, or garbage twice).
# Exit 2: usage error.
#
# The judge computes `overall` and applies the red-flag cap itself; this
# script validates the verdict's shape and never recomputes a score.

set -uo pipefail

RUBRIC="" PERSONA="" PLAN="" OUT="" TIMEOUT=120 JUDGES=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --rubric)  RUBRIC="${2:?--rubric needs a file}"; shift 2 ;;
        --persona) PERSONA="${2:?--persona needs a file}"; shift 2 ;;
        --plan)    PLAN="${2:?--plan needs a file}"; shift 2 ;;
        --out)     OUT="${2:?--out needs a path}"; shift 2 ;;
        --timeout) TIMEOUT="${2:?--timeout needs seconds}"; shift 2 ;;
        --judges)  JUDGES="${2:?--judges needs a count}"; shift 2 ;;
        *) echo "usage error: unknown flag: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$RUBRIC" ] || [ -z "$PERSONA" ] || [ -z "$PLAN" ] || [ -z "$OUT" ]; then
    echo "usage error: --rubric, --persona, --plan and --out are all required" >&2
    exit 2
fi
for f in "$RUBRIC" "$PERSONA" "$PLAN"; do
    [ -f "$f" ] || { echo "usage error: file not found: $f" >&2; exit 2; }
done

OUT_DIR=$(dirname "$OUT")
mkdir -p "$OUT_DIR"
PROMPT_FILE="$OUT_DIR/judge-prompt.txt"

# The prompt travels through a file and stdin, never argv: rubric + plan can
# exceed the ~32KB argv limit on Windows. Saving it also answers "what did
# the judge actually see" when a verdict looks odd.
{
    cat <<'EOF'
You are an experienced strength coach reviewing one generated training plan
for one person. Judge it against the rubric below.

Respond with ONE JSON object and nothing else — no prose around it, no
markdown fences, no tool use. Exact shape:

{
  "criteria": [
    {"name": "selection_suitability", "evidence": "...", "reasoning": "...", "score": N},
    {"name": "balance_and_coverage", "evidence": "...", "reasoning": "...", "score": N},
    {"name": "ordering_and_structure", "evidence": "...", "reasoning": "...", "score": N},
    {"name": "persona_fit", "evidence": "...", "reasoning": "...", "score": N},
    {"name": "red_flags", "evidence": "...", "reasoning": "...", "score": N}
  ],
  "red_flags": ["each thing a coach would veto outright — empty if none"],
  "overall": N,
  "summary": "one paragraph for the report table"
}

Keep the criteria in exactly this order with exactly these names. Scores are
integers 1-5. For each criterion write the evidence — citing specific
exercises, days or table rows — and the reasoning BEFORE choosing the score.
Compute overall yourself; if red_flags is non-empty, cap overall at 2.
EOF
    echo ""
    echo "=== RUBRIC ==="
    cat "$RUBRIC"
    echo ""
    echo "=== THE PERSON ==="
    cat "$PERSONA"
    echo ""
    echo "=== THE PLAN ==="
    cat "$PLAN"
} > "$PROMPT_FILE"

# Extract + validate one raw CLI response into a parsed verdict. Python
# because the repo already requires it — no jq, no new dependencies.
extract_verdict() {
    PYTHONIOENCODING=utf-8 python - "$1" "$2" <<'PY'
import json, re, sys

EXPECTED = ["selection_suitability", "balance_and_coverage",
            "ordering_and_structure", "persona_fit", "red_flags"]

def bail(reason):
    print(f"invalid verdict: {reason}", file=sys.stderr)
    sys.exit(1)

try:
    raw = open(sys.argv[1], encoding="utf-8").read()
except OSError as e:
    bail(str(e))
try:
    envelope = json.loads(raw)
except json.JSONDecodeError:
    bail("CLI output is not the --output-format json envelope")
text = envelope.get("result") if isinstance(envelope, dict) else None
if not isinstance(text, str):
    bail("envelope has no result text")
text = text.strip()
fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
if fenced:
    text = fenced.group(1)
try:
    v = json.loads(text)
except json.JSONDecodeError:
    bail("judge text is not JSON")
crits = v.get("criteria")
if not isinstance(crits, list) or [c.get("name") for c in crits] != EXPECTED:
    bail(f"criteria must be exactly {EXPECTED}, in order")
for c in crits:
    if not isinstance(c.get("evidence"), str) or not c["evidence"].strip():
        bail(f"{c['name']}: evidence missing")
    if not isinstance(c.get("reasoning"), str) or not c["reasoning"].strip():
        bail(f"{c['name']}: reasoning missing")
    if not isinstance(c.get("score"), int) or not 1 <= c["score"] <= 5:
        bail(f"{c['name']}: score must be an integer 1-5")
flags = v.get("red_flags")
if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
    bail("red_flags must be a list of strings")
overall = v.get("overall")
if not isinstance(overall, (int, float)) or not 1 <= overall <= 5:
    bail("overall must be a number 1-5")
if flags and overall > 2:
    bail("red flags present but overall not capped at 2")
if not isinstance(v.get("summary"), str) or not v["summary"].strip():
    bail("summary missing")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(v, f, indent=2, ensure_ascii=False)
PY
}

# One judging: call the CLI, extract; one retry on garbage or CLI failure.
# -k makes the deadline real — the CLI does not die on SIGTERM.
judge_once() {
    local parsed="$1" prefix="$2"
    local attempt raw rc
    for attempt in 1 2; do
        raw="$prefix-attempt-$attempt.json"
        timeout -k 10 "$TIMEOUT" "${CLAUDE_BIN:-claude}" -p --output-format json \
            < "$PROMPT_FILE" > "$raw" 2>&1
        rc=$?
        if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
            REASON="judge timed out after ${TIMEOUT}s"
            continue
        fi
        if [ "$rc" -ne 0 ]; then
            REASON="judge CLI exited $rc"
            continue
        fi
        if extract_verdict "$raw" "$parsed"; then
            return 0
        fi
        REASON="judge output unparseable after retry"
    done
    return 1
}

REASON=""
PARSED=()
for i in $(seq 1 "$JUDGES"); do
    parsed="$OUT_DIR/judge-$i-verdict.json"
    if ! judge_once "$parsed" "$OUT_DIR/judge-$i"; then
        # Infra noise must never masquerade as a quality signal: the verdict
        # says indeterminate and carries no scores at all.
        printf '{"outcome": "indeterminate", "reason": "%s"}\n' \
            "$REASON (judging $i of $JUDGES)" > "$OUT"
        echo "indeterminate: $REASON" >&2
        exit 1
    fi
    PARSED+=("$parsed")
done

# Final verdict: the single parsed verdict as-is, or the per-criterion
# median across N judges (evidence/reasoning/summary kept from judging 1 —
# the numbers are aggregated, the prose is a sample).
PYTHONIOENCODING=utf-8 python - "$OUT" "${PARSED[@]}" <<'PY'
import json, statistics, sys

runs = [json.load(open(p, encoding="utf-8")) for p in sys.argv[2:]]
v = dict(runs[0])
v["outcome"] = "scored"
if len(runs) > 1:
    for i, crit in enumerate(v["criteria"]):
        crit["score"] = statistics.median(r["criteria"][i]["score"] for r in runs)
    v["overall"] = statistics.median(r["overall"] for r in runs)
    flags = []
    for r in runs:
        for f in r["red_flags"]:
            if f not in flags:
                flags.append(f)
    v["red_flags"] = flags
    if flags and v["overall"] > 2:
        v["overall"] = 2
    v["judges"] = len(runs)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(v, f, indent=2, ensure_ascii=False)
PY
echo "scored: $OUT"
exit 0
```

- [ ] **Step 4: Run the tests**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: all judge.sh assertions PASS (the runner smoke section arrives in Task 5).

- [ ] **Step 5: Commit**

```bash
git add evals/judge.sh tests/skills/test-eval-harness.sh
git commit -m "evals: judge.sh — rubric prompt, verdict validation, retry, median"
```

---

### Task 5: run-evals.sh and the report

**Files:**
- Create: `evals/run-evals.sh`
- Modify: `tests/skills/test-eval-harness.sh` (append the runner section before `finish_tests`)

**Interfaces:**
- Consumes: `generate.py` CLI (exit 0/2/3; `--write` + `--write-md`; `--today`), `judge.sh` (Task 4 contract), persona folders (Task 3), rubric (Task 2).
- Produces: `bash evals/run-evals.sh [--persona NAME] [--skip-judge] [--judges N] [--timeout N] [--dataset-dir DIR] [--results-dir DIR]`; a fresh `results/<stamp>[-n]/` per run with per-persona artifacts and `report.md`. Exit 0 = every persona reached scored/generation-failed (or generated, under `--skip-judge`); exit 1 = ≥1 indeterminate; exit 2 = preflight/usage failure.

- [ ] **Step 1: Append the failing runner tests** (before `finish_tests`):

```bash
echo "run-evals.sh: smoke — one persona, fixture dataset, fake judge"
mkdir -p "$PROJECT/dataset/data"
cp "$FIXTURE" "$PROJECT/dataset/data/exercises.json"
rm -f "$PROJECT/calls.log"
out=$(CLAUDE_BIN="$PROJECT/good-judge" bash "$RUNNER" --persona beginner-liam \
    --dataset-dir "$PROJECT/dataset" --results-dir "$PROJECT/results" 2>&1)
code=$?
assert_exit_code 0 "$code" "a clean run exits 0"
run_dir=$(ls -d "$PROJECT/results"/*/ 2>/dev/null | head -1)
if [ -n "$run_dir" ]; then
    _pass "a dated run folder was created"
else
    _fail "a dated run folder was created"
fi
assert_file_contains "$run_dir/beginner-liam/plan.json" '"sessions"' "the plan JSON landed"
assert_file_contains "$run_dir/beginner-liam/plan.md" "## Weekly volume" "the plan render landed"
assert_file_contains "$run_dir/beginner-liam/verdict.json" '"outcome": "scored"' "the verdict landed"
assert_file_contains "$run_dir/report.md" "beginner-liam" "the report names the persona"
assert_file_contains "$run_dir/report.md" "FIXTURE-SUMMARY" "the report carries the judge summary"
assert_file_contains "$run_dir/report.md" "Weakest criterion" "the report points at the next tuning target"
echo ""

echo "run-evals.sh: --skip-judge needs no CLI at all"
out=$(CLAUDE_BIN="$PROJECT/does-not-exist" bash "$RUNNER" --persona beginner-liam \
    --skip-judge --dataset-dir "$PROJECT/dataset" --results-dir "$PROJECT/results2" 2>&1)
code=$?
assert_exit_code 0 "$code" "--skip-judge exits 0 without a CLI"
run_dir2=$(ls -d "$PROJECT/results2"/*/ 2>/dev/null | head -1)
assert_file_contains "$run_dir2/beginner-liam/plan.json" '"sessions"' "the plan still lands"
assert_file_absent "$run_dir2/beginner-liam/verdict.json" "no verdict without a judge"
assert_file_contains "$run_dir2/report.md" "not judged" "the report says the persona was not judged"
echo ""

echo "run-evals.sh: preflights"
out=$(bash "$RUNNER" --skip-judge --dataset-dir "$PROJECT/no-dataset" \
    --results-dir "$PROJECT/results3" 2>&1)
code=$?
assert_exit_code 2 "$code" "a missing dataset dir fails preflight"
assert_contains "$out" "git clone" "and hands back the exact clone command"
out=$(bash "$RUNNER" --persona nobody --skip-judge \
    --dataset-dir "$PROJECT/dataset" --results-dir "$PROJECT/results3" 2>&1)
code=$?
assert_exit_code 2 "$code" "an unknown persona is a usage error"
assert_contains "$out" "unknown persona" "and is named"
```

- [ ] **Step 2: Run to verify failure**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: judge section PASS, runner section FAIL (`run-evals.sh` missing).

- [ ] **Step 3: Write `evals/run-evals.sh`**

```bash
#!/usr/bin/env bash
# Generate a plan for every persona, judge each against the rubric, compose
# a comparison report. Scores are for eyes, not exit codes: the exit status
# reflects infrastructure only.
#
#   0  every persona reached a verdict (scored / generation-failed, or
#      generated under --skip-judge)
#   1  at least one persona came back indeterminate — infra noise, see report
#   2  preflight or usage failure; nothing (or nothing more) was run
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GENERATE="$REPO_ROOT/skills/generation/scripts/generate.py"
PERSONAS_DIR="$SCRIPT_DIR/personas"
RUBRIC="$SCRIPT_DIR/rubric/plan-quality.md"

PERSONA="" SKIP_JUDGE=false JUDGES=1 TIMEOUT=120
DATASET_DIR="$REPO_ROOT/datasets/exercises-dataset"
RESULTS_DIR="$SCRIPT_DIR/results"

usage() {
    echo "Usage: $0 [--persona NAME] [--skip-judge] [--judges N] [--timeout SECONDS]"
    echo "          [--dataset-dir DIR] [--results-dir DIR]"
    echo ""
    echo "See evals/README.md for requirements and the tuning loop."
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --persona)     PERSONA="${2:?--persona needs a name}"; shift 2 ;;
        --skip-judge)  SKIP_JUDGE=true; shift ;;
        --judges)      JUDGES="${2:?--judges needs a count}"; shift 2 ;;
        --timeout)     TIMEOUT="${2:?--timeout needs seconds}"; shift 2 ;;
        --dataset-dir) DATASET_DIR="${2:?--dataset-dir needs a path}"; shift 2 ;;
        --results-dir) RESULTS_DIR="${2:?--results-dir needs a path}"; shift 2 ;;
        --help|-h)     usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# Preflights — fail before any work, with the fix in hand.
if [ ! -d "$DATASET_DIR" ]; then
    echo "ERROR: dataset not found at $DATASET_DIR" >&2
    echo "Clone it first:" >&2
    echo "  git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset" >&2
    exit 2
fi
if [ "$SKIP_JUDGE" = false ] && ! "${CLAUDE_BIN:-claude}" --version > /dev/null 2>&1; then
    echo "ERROR: the Claude Code CLI is not available — see evals/README.md" >&2
    echo "(--skip-judge runs the generation half without it)" >&2
    exit 2
fi

personas=()
if [ -n "$PERSONA" ]; then
    if [ ! -d "$PERSONAS_DIR/$PERSONA" ]; then
        echo "ERROR: unknown persona: $PERSONA" >&2
        echo "Known personas:" >&2
        ls "$PERSONAS_DIR" | sed 's/^/  /' >&2
        exit 2
    fi
    personas=("$PERSONA")
else
    for d in "$PERSONAS_DIR"/*/; do
        personas+=("$(basename "$d")")
    done
fi
if [ "${#personas[@]}" -eq 0 ]; then
    echo "ERROR: no personas under $PERSONAS_DIR" >&2
    exit 2
fi

# A fresh dated folder per run — never overwritten, suffixed on collision.
STAMP=$(date +%Y-%m-%d-%H%M)
RUN_DIR="$RESULTS_DIR/$STAMP"
n=2
while [ -e "$RUN_DIR" ]; do
    RUN_DIR="$RESULTS_DIR/$STAMP-$n"
    n=$((n + 1))
done
mkdir -p "$RUN_DIR"
TODAY=$(date +%Y-%m-%d)

INDETERMINATE=0
for name in "${personas[@]}"; do
    pdir="$PERSONAS_DIR/$name"
    out="$RUN_DIR/$name"
    mkdir -p "$out"
    echo "== $name"

    args=(--profile "$pdir/profile.json" --program "$pdir/program.json"
          --dataset-dir "$DATASET_DIR" --today "$TODAY"
          --write "$out/plan.json" --write-md "$out/plan.md")
    if [ -f "$pdir/rules.json" ]; then
        args+=(--rules "$pdir/rules.json")
    fi

    # A refusal (exit 2/3) is a real finding, not an infra failure: keep the
    # stderr verbatim — generate.py's messages already name the file to fix.
    if ! gen_out=$(PYTHONIOENCODING=utf-8 python "$GENERATE" "${args[@]}" 2>&1); then
        printf '%s\n' "$gen_out" > "$out/gen-error.txt"
        echo "   generation-failed (see $out/gen-error.txt)"
        continue
    fi

    if [ "$SKIP_JUDGE" = true ]; then
        echo "   generated (judge skipped)"
        continue
    fi

    if bash "$SCRIPT_DIR/judge.sh" --rubric "$RUBRIC" \
            --persona "$pdir/persona.yaml" --plan "$out/plan.md" \
            --out "$out/verdict.json" --timeout "$TIMEOUT" --judges "$JUDGES" \
            > /dev/null; then
        echo "   scored"
    else
        INDETERMINATE=$((INDETERMINATE + 1))
        echo "   indeterminate"
    fi
done

# The report is derived entirely from what landed on disk — no state
# threaded through bash: gen-error.txt means generation-failed, a verdict
# carries its own outcome, a plan with neither was generated but not judged.
PYTHONIOENCODING=utf-8 python - "$RUN_DIR" <<'PY'
import json, sys
from pathlib import Path

CRITERIA = ["selection_suitability", "balance_and_coverage",
            "ordering_and_structure", "persona_fit", "red_flags"]
HEADERS = ["Selection", "Balance", "Ordering", "Persona fit", "Red flags"]

run_dir = Path(sys.argv[1])
rows, summaries, failures, indeterminates, scored = [], [], [], [], []
for pdir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
    name = pdir.name
    gen_err = pdir / "gen-error.txt"
    verdict_file = pdir / "verdict.json"
    if gen_err.exists():
        rows.append((name, None, "generation-failed"))
        failures.append((name, gen_err.read_text(encoding="utf-8")))
    elif verdict_file.exists():
        v = json.loads(verdict_file.read_text(encoding="utf-8"))
        if v.get("outcome") == "scored":
            rows.append((name, v, None))
            scored.append((name, v))
            summaries.append((name, v["summary"]))
        else:
            rows.append((name, None, "indeterminate"))
            indeterminates.append((name, v.get("reason", "unknown")))
    else:
        rows.append((name, None, "generated — not judged"))

lines = [f"# Eval run {run_dir.name}", ""]
lines.append("| Persona | " + " | ".join(HEADERS) + " | Overall | Flags |")
lines.append("|---" * 8 + "|")
for name, v, status in rows:
    if v is None:
        lines.append(f"| {name} | " + " | ".join(["—"] * 5) + f" | {status} | — |")
    else:
        by = {c["name"]: c["score"] for c in v["criteria"]}
        cells = " | ".join(str(by[c]) for c in CRITERIA)
        lines.append(f"| {name} | {cells} | {v['overall']} | {len(v['red_flags'])} |")
lines.append("")
if summaries:
    lines += ["## Judge summaries", ""]
    for name, s in summaries:
        lines += [f"**{name}** — {s}", ""]
if indeterminates:
    lines += ["## Indeterminate", ""]
    lines += [f"- {name}: {reason}" for name, reason in indeterminates]
    lines.append("")
if failures:
    lines += ["## Generation failures", ""]
    for name, err in failures:
        lines += [f"### {name}", "", "```", err.rstrip(), "```", ""]
if scored:
    means = {
        c: sum({x["name"]: x["score"] for x in v["criteria"]}[c]
               for _, v in scored) / len(scored)
        for c in CRITERIA
    }
    worst = min(means, key=means.get)
    lines += [f"Weakest criterion across the matrix: **{worst}** "
              f"(mean {means[worst]:.1f}) — the next tuning target.", ""]
(run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {run_dir / 'report.md'}")
PY

echo ""
echo "run folder: $RUN_DIR"
if [ "$INDETERMINATE" -gt 0 ]; then
    echo "STATUS: $INDETERMINATE persona(s) indeterminate — infra noise, see the report"
    exit 1
fi
echo "STATUS: OK"
exit 0
```

- [ ] **Step 4: Run the tests**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: PASS end to end.

- [ ] **Step 5: Commit**

```bash
git add evals/run-evals.sh tests/skills/test-eval-harness.sh
git commit -m "evals: runner — preflights, per-persona pipeline, report, exit codes"
```

---

### Task 6: Wire into the suite and verify the whole

**Files:**
- Modify: `tests/skills/run-skill-tests.sh` (the `tests` array, ~line 77-85, and the `--help` text, ~line 52-59)

**Interfaces:**
- Consumes: `test-eval-harness.sh` (Tasks 4-5). The runner fails on listed-but-missing files, so the name must match exactly.

- [ ] **Step 1: Register the test file**

In the offline `tests=(…)` array, after `"test-generation-script.sh"`:

```bash
    "test-eval-harness.sh"
```

In the `--help` offline list, after the `test-generation-script.sh` line:

```bash
            echo "  test-eval-harness.sh       evals/ plumbing — judge.sh and the runner, offline"
```

- [ ] **Step 2: Run the full offline suite**

Run: `bash tests/skills/run-skill-tests.sh`
Expected: `STATUS: PASSED`, with `test-eval-harness.sh` in the list.

- [ ] **Step 3: Run the validator**

Run: `python scripts/validate-skills.py`
Expected: exit 0 — evals touched nothing it validates.

- [ ] **Step 4: One real run (needs the cloned dataset; judging needs the CLI)**

Run: `bash evals/run-evals.sh --skip-judge` then, if the diff of plans looks sane, `bash evals/run-evals.sh`
Expected: seven plans; a `report.md` whose weakest-criterion line points somewhere plausible. Results stay untracked.

- [ ] **Step 5: Commit**

```bash
git add tests/skills/run-skill-tests.sh
git commit -m "tests: register the eval-harness suite"
```

---

## Review checklist (for reviewing Samy's implementation)

Contracts that must hold whatever shape his code takes; everything else is style:

1. **Boundaries** — nothing under `skills/` or `profile/` changed; `evals/results/` ignored; no numbers invented in `evals/` (the pipeline consumes, never tunes).
2. **One owner per number** — persona volume blocks came from `volume.py --write`, not by hand; the runner passes program files through untouched.
3. **Three-valued outcomes** — indeterminate can never carry a score; generation-failed shows stderr verbatim; only infra drives the exit code.
4. **Judge reliability** — evidence/reasoning before score in the prompt; one persona per call; fixed criterion order validated; retry exactly once; timeout enforced with `-k`; verdict shape validated, scores never recomputed by the runner (median aggregation inside judge.sh is the one sanctioned aggregation).
5. **Offline testability** — every failure path testable via `CLAUDE_BIN` fakes; the smoke test runs on the bundled fixture; no test needs the network or a token.
6. **Windows survival** — prompt via stdin-from-file (argv limit); `PYTHONIOENCODING=utf-8` on emoji-printing python; no jq.
7. **Docs** — README documents the CLI requirement (vendor-neutral folder name), the clone command matches CLAUDE.md's, tuning loop described; the schema deviation (3-day minimum, not 2) is honored, not "fixed" by loosening a schema.
