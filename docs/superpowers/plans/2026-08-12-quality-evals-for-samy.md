# Quality Evals — Implementation Plan (Samy's copy)

This is the plan you implement yourself. It tells you what to build, in what
order, what to watch out for, and how to know each milestone is done — but the
code is yours to write. Claude's detailed reference plan lives next to this
file (`2026-08-12-quality-evals-reference.md`); your code gets reviewed
against it when you push. Peeking is allowed but defeats the point.

Spec: `docs/superpowers/specs/2026-08-12-quality-evals-design.md`. Read it
once before starting — everything below is "how", the spec is "what and why".

**One deviation from the spec, found during planning:** the spec's persona
matrix says "days per week (2–6)" and calls for a 2-day edge-case persona.
That persona cannot exist: `program.schema.json` sets `days_per_week`
minimum 3, and `volume.py` only accepts `--days 3..7`. The awkward persona is
a 3-day / minimal-equipment / 20-40-minute one instead, and the axis is 3–6.

## Ground rules (from the repo, they all apply here)

- `evals/` is a pure consumer of the skills: it never edits anything under
  `skills/`, never writes under `profile/`, and owns no tuning numbers.
- `evals/results/` is throwaway output — gitignore it like `datasets/`.
- Bash files follow the `tests/skills` conventions: `set -uo pipefail`,
  python for anything JSON (no jq, no new dependencies).
- Windows gotchas you already fought once in `tests/skills`: pipe
  `PYTHONIOENCODING=utf-8` into every python call that may print an emoji,
  and use `timeout -k 10` so deadlines are enforced, not just reported.
- Commit after every milestone. Small commits, no trailers beyond
  Co-Authored-By if any.

---

## Milestone 1 — Scaffold

Create the skeleton so everything after has a home:

- `evals/README.md` — requirements and how-to-run. Write it properly now, not
  as a stub: requirements (python, bash, the Claude Code CLI logged in, the
  cloned dataset with the exact `git clone` command), the four run commands
  from the spec's Runner UX section, the three per-persona outcomes, and the
  intended tuning loop (tweak config → `--skip-judge` → diff plans → judge
  when the diff looks interesting). This file is also where the vendor
  requirement is documented — the folder name stays vendor-neutral.
- Append `evals/results/` to the root `.gitignore`, with a one-line comment
  in the same voice as the existing entries.

**Done when:** `git status` shows only the new README and the `.gitignore`
edit; a file dropped into `evals/results/` does not show up as untracked.

## Milestone 2 — Rubric

`evals/rubric/plan-quality.md`. The judge receives this file verbatim, so
write it as instructions to a reader, not notes to yourself.

Five criteria, in this fixed order, with these exact machine names (the
runner will validate verdicts against them — pick them now and never drift):

1. `selection_suitability`
2. `balance_and_coverage`
3. `ordering_and_structure`
4. `persona_fit`
5. `red_flags`

For each criterion write anchor descriptions: what a 5 looks like, what a 1
looks like (a 3 anchor helps too). End the file by reminding the judge what
is *out* of scope (schema validity, volume arithmetic, dataset membership —
deterministically owned elsewhere) and that any red flag caps overall at 2.

**Done when:** you can read the file cold and score a plan with it yourself,
without needing anything that isn't in the file.

## Milestone 3 — Personas

Seven folders under `evals/personas/<slug>/`, each holding:

- `profile.json` — copy `skills/onboarding/examples/profile.example.json`,
  mutate. Must stay valid against `profile.schema.json` (watch the enums:
  gym types, bodyfat brackets, experience levels).
- `program.json` — hand-write the `program` block (schema-valid: split is
  only `full_body` or `upper_lower`, goal only
  `hypertrophy`/`strength`/`both`, session minutes from the enum), then let
  volume.py fill the volume block **in place** — that's the one-owner rule:

  ```bash
  python skills/onboarding/scripts/volume.py \
      --profile evals/personas/<slug>/profile.json \
      --today 2026-08-12 --write evals/personas/<slug>/program.json
  ```

  Pin `--today` to today's date so the checked-in file never depends on when
  you regenerate it.
- `persona.yaml` — the narrative: name, story, goal detail, constraints,
  preferences, and an empty `interview_answers: {}` as the phase-2 hook.
  Every persona carries at least one injury or goal detail so `persona_fit`
  has something to bite on.
- `rules.json` — only for the one "meaty rules" persona (mirror the shape of
  `skills/generation/examples/rules.example.json`; exclusions must name real
  dataset values or you'll get warnings, which is itself interesting).

Cover the axes: experience beginner→advanced, commercial vs home gym, days
3–6, all three goals, short and long sessions, both splits, one meaty
rules.json persona, one deliberately awkward persona (3 days, garage gym
with almost nothing, `20-40` sessions — shortfall country). Give one
home-gym persona a constraint that lives **only** in the narrative (e.g. a
shoulder that hates overhead pressing) — the generator can't see it, the
judge can, and that gap is exactly the future-feature signal criterion 4 is
designed to surface.

**Verify each persona generates** before calling this done — offline, using
the bundled fixture as the dataset, same trick `test-generation-script.sh`
uses (the descriptor expects `data/exercises.json` inside the dataset dir):

```bash
TMP=$(mktemp -d) && mkdir -p "$TMP/data"
cp skills/generation/scripts/generate.fixture.json "$TMP/data/exercises.json"
python skills/generation/scripts/generate.py \
    --profile evals/personas/<slug>/profile.json \
    --program evals/personas/<slug>/program.json \
    --dataset-dir "$TMP" --today 2026-08-12   # add --rules where it exists
```

**Done when:** all seven exit 0 (a `short:` warning is fine — one persona is
built to produce them; an exit-3 refusal is not).

## Milestone 4 — judge.sh (test-driven)

Write `tests/skills/test-eval-harness.sh` FIRST, then make it pass. The fake
CLI pattern from `test-agent-harness.sh` is your template: `CLAUDE_BIN`
points at a small fake script, so every failure path runs offline and free.

The contract to design and then pin with tests:

- Inputs: rubric file, persona.yaml, plan.md, output path; optional timeout
  (default 120) and judges count (default 1). `CLAUDE_BIN` overrides the CLI.
- Builds ONE prompt: fixed instructions + the exact verdict JSON shape +
  rubric + persona + plan. Instructions say: evidence and reasoning BEFORE
  each score, exact criterion names in exact order, judge computes `overall`
  and applies the red-flag cap itself, no tools, output pure JSON.
- Calls `claude -p --output-format json`. Two traps here:
  - The CLI's output is an *envelope* — a JSON object whose `result` field
    holds the judge's text. Parse the envelope with python, then parse
    `result` as the verdict (tolerate the model wrapping it in ``` fences).
  - Pass the prompt via **stdin from a file**, not as an argv parameter —
    rubric + plan can blow past Windows' ~32KB argv limit.
- Validates the verdict: five criteria with the exact names in order,
  integer scores 1–5, non-empty evidence and reasoning, `red_flags` a list,
  `overall` a number, cap respected, `summary` non-empty.
- Failure ladder per judging: bad output → one retry → give up. On give-up,
  still write a verdict file `{"outcome": "indeterminate", "reason": ...}`
  and exit 1. On success write the verdict with `"outcome": "scored"` and
  exit 0. Timeout (enforced with `timeout -k 10`) is indeterminate too.
- `--judges N`: N independent judgings, per-criterion median, median
  overall, union of red flags. Any judging failing twice → indeterminate.
- Save the prompt and each raw CLI response next to the verdict — when a run
  goes indeterminate you'll want to see what actually happened.

Tests to write (all with fakes): valid verdict → exit 0, `scored`; garbage
→ called exactly twice (count calls in a log file), exit 1, `indeterminate`;
garbage-then-valid → retry recovers, exit 0; a fake that sleeps → timeout
enforced, indeterminate; `--judges 3` with varying scores → median lands.

**Done when:** `bash tests/skills/test-eval-harness.sh` passes, and a manual
run against one persona's generated plan with the real CLI produces a
verdict you believe.

## Milestone 5 — run-evals.sh + report

The orchestrator. Flags: `--persona NAME`, `--skip-judge`, `--judges N`,
`--timeout N` — plus `--dataset-dir` and `--results-dir` overrides (defaults
`datasets/exercises-dataset` and `evals/results`), which exist so the smoke
test can point everything at temp dirs.

- Preflights: dataset dir exists (else print the exact clone command and
  exit), CLI answers `--version` (skipped under `--skip-judge`).
- Fresh run folder `results/<YYYY-MM-DD-HHMM>/` — if it already exists,
  suffix `-2`, `-3`; never overwrite.
- Per persona: `generate.py` with `--today` = the run date, `--rules` only
  if the persona has one, writing `plan.json` + `plan.md` into the run
  folder. Exit non-zero → save stderr verbatim to `gen-error.txt`, outcome
  `generation-failed`, move on. Then judge.sh unless `--skip-judge`.
- `report.md` (compose with an embedded python heredoc): one table —
  personas as rows, five criteria columns, overall, red-flag count; failed/
  indeterminate personas keep their row with the status in place of scores.
  Then each judge summary, then generation stderr verbatim, then the closing
  "weakest criterion across the matrix" line (lowest mean among scored).
  Tip: derive each persona's outcome from what's on disk (`gen-error.txt`
  present / `verdict.json` outcome field / plan only) rather than threading
  state through bash.
- Exit code is infrastructure only: preflight failure or any indeterminate
  → non-zero; generation-failed is a *finding*, not an infra failure → 0.

Add to the test file: one smoke test — one persona, fixture dataset dir,
fake judge, temp results dir → exit 0, all four files land, report contains
the persona and the fake's summary. Plus: `--skip-judge` works with no CLI
at all, and a missing dataset dir fails preflight mentioning `git clone`.

**Done when:** the smoke tests pass, and a real
`bash evals/run-evals.sh --skip-judge` against the cloned dataset produces
seven plans and a report.

## Milestone 6 — Wire in and finish

- Register `test-eval-harness.sh` in `run-skill-tests.sh`: the offline
  `tests` array AND the `--help` text (the runner fails on missing listed
  files, so the name must be exact).
- Full check: `python scripts/validate-skills.py` still exits 0 (evals
  touched nothing it validates), `bash tests/skills/run-skill-tests.sh`
  green.
- The real thing: `bash evals/run-evals.sh` with the cloned dataset and the
  real CLI. Read `report.md`. Does the weakest-criterion line point
  somewhere plausible? That's the pipeline's first real signal.

**Done when:** suite green, one real judged run committed to memory (not to
git — results are ignored), and the branch is ready for review.
