# Quality Evals for Workout Generation — Design

Date: 2026-08-12
Status: approved pending review
Scope: this spec covers the plan-quality eval pipeline only. The test-suite restructure
(layered unit/integration folders, removing `--self-test` from the scripts) is a separate
follow-up spec. Agent-in-the-loop evals for onboarding (user simulator) are phase 2.

## Problem

The repo's tests and validator pin everything deterministic: schemas, script CLIs,
byte-for-byte fixture output, prose policy. None of them answer the question that actually
drives tuning: *is the generated plan a plan a good coach would hand this person?* Today
that judgment is manual — generate a plan, read it, tweak `volume.config.json` /
`generate.config.json` / `datasets.json`, repeat. It is slow, and there is no record of
whether a tweak made the other personas' plans worse.

## Goal

An automated pipeline that generates plans for a fixed matrix of sample people, has an LLM
judge score each plan against a written rubric, and composes a comparison report — so a
config tweak can be evaluated across the whole matrix in one command.

Non-goals: gating CI on scores (scores are for eyes, not exit codes); re-checking anything
the validator or `generate.py` already owns; evaluating agent behaviour (phase 2);
restructuring existing tests.

## Shape

Model: the hybrid pattern used by superpowers-evals and current LLM-as-judge practice —
deterministic checks own everything verifiable, an LLM judge with an anchored rubric owns
quality, and infra failure is a third verdict (`indeterminate`) that never masquerades as
a quality signal.

Key insight the design leans on: plan content is fully deterministic given profile +
program + rules + dataset (`generate.py --today` pins the date). No agent is needed to
produce the artifact being judged. The only LLM in the loop is the judge.

## Layout

```
evals/
  README.md                      requirements (Claude Code CLI, cloned dataset), how to run
  personas/<name>/               one folder per sample person, checked in
    persona.yaml                 narrative: story, goal detail, injuries, preferences;
                                 future: scripted interview answers for phase-2 onboarding evals
    profile.json                 valid against skills/onboarding/schema/profile.schema.json
    program.json                 valid against program.schema.json, volume block included
    rules.json                   optional, personal generation rules
  rubric/plan-quality.md         the judge rubric, prose, received verbatim by the judge
  run-evals.sh                   the runner (bash, tests/skills conventions: set -uo pipefail)
  judge.sh                       rubric + persona.yaml + plan.md → claude -p → verdict.json
  results/                       gitignored, like datasets/
    <YYYY-MM-DD-HHMM>/
      <persona>/plan.json plan.md verdict.json
      report.md
```

Boundaries:
- `evals/` never writes under `profile/` — personas are checked-in test data, not user data.
- The pipeline is a pure consumer of the skills: no edits to `skills/`, no numbers of its own.
- `results/` and its dated run folders are never overwritten; each run gets a fresh folder.
- The folder is not named after the vendor; the Claude Code CLI requirement is documented in
  `evals/README.md` and enforced by a runner preflight.

## Per-persona flow

1. `python skills/generation/scripts/generate.py --profile … --program … --rules … \
   --dataset-dir datasets/exercises-dataset --today <run date> \
   --write results/<run>/<persona>/plan.json --write-md …/plan.md`
2. `judge.sh` builds one prompt — rubric + persona.yaml + plan.md (plan.md already carries
   the volume table and shortfall warnings) — and calls `claude -p --output-format json`,
   no tools allowed. The judge's text must be pure JSON; the runner extracts and parses it
   with python (already a repo requirement; no jq, no new dependencies).
3. Verdict JSON is validated for required keys. Missing/unparseable → one retry →
   `indeterminate`.
4. After all personas: compose `report.md`.

Outcome per persona is three-valued:
- `scored` — generator ran, judge returned valid JSON.
- `generation-failed` — `generate.py` refused (exit 2/3). A real finding: the report shows
  its stderr verbatim (the messages already name the file to fix).
- `indeterminate` — judge timed out or emitted garbage twice. Infra noise; reported,
  never scored.

## Rubric

`evals/rubric/plan-quality.md`. Five criteria, each scored 1–5 against written anchor
descriptions (what a 5 looks like, what a 1 looks like). Editing the file changes what
"good" means; judge code never changes.

1. Selection suitability — exercises match experience and equipment; no redundant
   near-duplicates eating slots.
2. Balance and coverage — week-level push/pull/hinge balance; no muscle trained hard on
   back-to-back days against the split's intent.
3. Ordering and session structure — compounds before isolation, sensible flow, plausible
   fit in the profile's session minutes.
4. Persona fit — the persona.yaml narrative (goal detail, injuries, preferences) honored
   in spirit; rules.json entries visibly respected. This criterion is the hook for future
   injury/goal features: richer narratives automatically sharpen it.
5. Red flags — anything a coach would veto outright. Any red flag caps overall at 2.

Out of rubric scope (deterministically owned elsewhere): schema validity, volume-target
satisfaction, exercise-exists-in-dataset, overwrite protection.

Judge reliability practices, baked into the prompt:
- per criterion: evidence (citing specific exercises/days) and reasoning BEFORE the score;
- personas judged independently, one per call — no cross-comparison in a single prompt;
- fixed criterion order; anchored scores for cross-run comparability;
- optional `--judges N`: run the judge N times, take the per-criterion median.

Verdict shape:

```json
{
  "criteria": [{"name": "...", "evidence": "...", "reasoning": "...", "score": 4}],
  "red_flags": [],
  "overall": 4.2,
  "summary": "one paragraph for the report table"
}
```

The judge computes `overall` and applies the red-flag cap itself; the runner validates
shape but never recomputes scores.

Known limitation, accepted: `claude -p` judges with whatever model the CLI resolves, so
absolute scores can drift when the CLI's model updates. Comparisons are therefore made
within a run (persona vs persona, before-tweak vs after-tweak in the same sitting), not
across long time spans.

## Runner UX

```bash
bash evals/run-evals.sh                     # all personas: generate + judge + report
bash evals/run-evals.sh --persona <name>    # one persona
bash evals/run-evals.sh --skip-judge        # generate only — free; for diffing plans
bash evals/run-evals.sh --judges 3          # median-of-3 judging
```

- Preflights: `claude --version` succeeds (else point at README), dataset dir exists (else
  print the exact clone command), `results/` writable. `--skip-judge` skips the CLI check.
- Judge calls run under an enforced timeout (default 120s, `--timeout` to override), using
  the same enforced-kill approach the existing `run_claude` harness pins.
- Exit code reflects infrastructure only: 0 = every persona reached a verdict, non-zero =
  something failed to run. Scores never gate.
- `--today` pinned to the run date: plans within a run are reproducible; diffs between two
  runs' plan files are pure signal (modulo the run date line).
- Intended tuning loop: tweak config → `--skip-judge` → diff plans against last run →
  judge only when the diff looks interesting.

## report.md

One table — personas as rows, the five criteria as columns, overall and red-flag count at
the end — then each judge's summary paragraph, then a closing "weakest criterion across
the matrix" line pointing at the next tuning target. `generation-failed` and
`indeterminate` personas appear in the table with their status in place of scores.

## Persona matrix (initial 7)

Built by copying and mutating the shipped examples. Axes covered: experience
(beginner/intermediate/advanced), gym (home/commercial), days per week (2–6), goal,
session length, split; plus one persona with a meaty rules.json (exclusions, muscle
focus) and one deliberately awkward edge case (2-day, minimal equipment, short sessions —
where shortfall handling shows). Every persona.yaml carries at least one injury or goal
detail now, so criterion 4 has something to bite on from day one.

Persona validity needs no separate validator: `generate.py`'s strict refusals are the
validation. (Optionally, a later follow-up can wire personas into `validate-skills.py`;
not part of this spec.)

## Testing the eval infra

Offline, in the existing suite's style:
- `judge.sh` under a fake CLI via the existing `CLAUDE_BIN` pattern: good JSON → scored;
  garbage JSON → one retry, then indeterminate; timeout → indeterminate.
- One runner smoke test: a single persona against the bundled
  `skills/generation/scripts/generate.fixture.json` dataset with a fake judge, asserting
  plan files land and a report composes.

Nothing else — generation correctness is already pinned by `test-generation-script.sh`.

## Future hooks (designed for, not built)

- persona.yaml carries narrative + scripted interview answers → phase-2 onboarding evals
  (user-simulator driving the real agent, superpowers-evals style).
- Criterion 4 sharpens automatically as personas gain injury/goal sections.
- A future "LLM fixes the plan" feature can be evaluated with the same rubric by judging
  before/after plans.
- The judge invocation is one thin script; swapping `claude -p` for an API-based judge
  changes `judge.sh` only.

## Decisions log

- Quality evals first, behavioral/agent evals later (user).
- Script-level subject under test; persona format future-proofed for agent evals (user, option 3).
- Test restructure is a separate follow-up spec (user, option 1).
- Judge via `claude -p`, no API dependency (user, option 1).
- Folder named `evals/`, vendor requirement documented + preflighted, not vendor-named (user).
- Implementation is learning-mode: a human-friendly step-by-step plan for Samy to
  implement, plus a detailed reference plan Claude reviews against.
