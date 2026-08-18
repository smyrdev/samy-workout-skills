# samy-workout-skills

Two portable skills: **onboarding** interviews you once about your training situation and saves
it; **generation** turns that into a concrete week of exercises, chosen against a per-muscle weekly
volume target using a real exercise dataset.

They are **skills**, not an app — markdown files of instructions any capable LLM agent can
follow, plus two small dependency-free Python scripts for the arithmetic. There is no server, no
account, and no install. The repository is the whole thing.

> Not medical advice. Everything here is self-reported and unverified — if you have an injury or a
> medical condition, talk to someone qualified before training around it.

## Quickstart

**In Claude Code**, from the repository root:

```
/onboard      # once: the interview
/generate     # every cycle: the workout plan
```

**With any other agent**, point it at the skill files and let it run:

> Read `skills/onboarding/SKILL.md` and follow it.
> Read `skills/generation/SKILL.md` and follow it.

Onboarding asks about twenty questions in five or six rounds, shows a summary before anything is
saved, and ends up with two files: `profile/profile.json` and
`profile/programs/program-<today>.json`.

Generation re-confirms your program answers ("same as last time" is one click), clones the
exercise dataset into a local cache, works out which exercises are legal for your weekly per-muscle set
allocation, shows you the week and the volume math before writing, and saves
`profile/plans/plan-<today>.json` plus a readable `plan-<today>.md`.

One repository holds one profile. If someone else wants to use these skills, they clone their own
copy — there is nothing to share and nothing to keep separate.

## What it asks

Two groups, because they change on a different schedule — see
[Where your data lives](#where-your-data-lives):

- **Profile** (asked once) — name, sex, date of birth, height, weight, bodyfat bracket, lifting
  and cardio experience, where you train, seven strength benchmarks
- **Program** (asked every cycle) — goal, days per week, session length, split, deload, a name and
  emoji for this training block

The program answers are saved even though they change from cycle to cycle. They are defaults, not
commitments: the generator shows them back and lets you change any of them for one cycle without
redoing the interview — or you can just run onboarding again, which writes a new dated program
file alongside the old one.

Nothing is written until you have seen a summary of every answer and the exact paths it is about
to write.

## Changing something later

```
/onboard --update
```

That asks only about the fields you name. A change to a profile field (body stats, gym,
experience) edits `profile.json` in place; a change to a program field (goal, days, split, ...)
writes a new dated file under `programs/` instead of touching the old one.

Run `/onboard` with no flag when a profile already exists and it stops to ask whether you meant to
change a few fields or start over — a fresh interview overwrites `profile.json`, so it is never
assumed.

## Hand-fill path — no interview

You can skip the interview entirely: copy the samples, edit them by hand using
[`docs/onboarding-fields.md`](docs/onboarding-fields.md) as a guide, and validate.

```bash
mkdir -p profile/programs
cp skills/onboarding/assets/examples/profile.example.json profile/profile.json
cp skills/onboarding/assets/examples/program.example.json profile/programs/program-2026-08-06.json
# edit both by hand
python scripts/validate-skills.py
```

That's a complete, schema-valid pair of files on its own — `volume` is optional. To fill it in:

```bash
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-2026-08-06.json
```

## The exercise dataset

Plans are built from
[smyrdev/exercises-dataset](https://github.com/smyrdev/exercises-dataset) — ~1,300 exercises
where most carry a per-muscle volume map (1.0 for prime movers, 0.5 for meaningful synergists).
Each set of an exercise adds its coefficients to your weekly per-muscle totals. The generator
works out which exercises you may legally be given and how many sets each muscle is owed; the
coach picks from that, and the generator then reports honestly which group falls short with your
equipment.

The dataset is cloned into a gitignored `datasets/` cache on first use. Everything the generator
knows about it — field names, equipment tiers, how its 22-muscle vocabulary maps onto the volume
model's 10 groups — lives in
[`skills/generation/assets/datasets.json`](skills/generation/assets/datasets.json). Point that file at a
different dataset and nothing else changes.

## Your rules

`profile/rules.md` is a hand-written file of standing preferences the generator reads
on every run: exercises or equipment to never use, muscle groups to focus or drop, how sessions
are ordered. It is plain Markdown — `## Section` headings and `- item` bullets, with any other
prose ignored as a note to yourself:

```markdown
## Exclude exercises
- burpee

## Focus muscles
- shoulders
```

Copy
[`skills/generation/assets/examples/rules.example.md`](skills/generation/assets/examples/rules.example.md)
and edit — [`docs/generation-fields.md`](docs/generation-fields.md) lists every section.
Typos are reported as warnings in the plan, never silently ignored.

## Where your data lives

`profile/` is gitignored in full. Your body stats are never committed, even by accident.

- `profile/profile.json` — who you are: body stats, experience, gym. Written once, updated in
  place when something about you changes.
- `profile/programs/program-<date>.json` — what you want this cycle: goal, days, split, and (once
  `volume.py` has run) a computed weekly per-muscle set allocation. One file per training block;
  the highest-dated filename is the current one.
- `profile/rules.md` — your standing generation preferences, written by you alone.
- `profile/plans/plan-<date>.json` + `.md` — generated plans, one dated pair per run, never
  overwritten. The `.md` is yours to scribble on.

The schema lives at
[`skills/onboarding/assets/schema/profile.schema.json`](skills/onboarding/assets/schema/profile.schema.json) and
[`skills/onboarding/assets/schema/program.schema.json`](skills/onboarding/assets/schema/program.schema.json),
with every field documented in [`docs/schema.md`](docs/schema.md).

Your files are plain JSON you can read, edit, back up, or delete. Nothing else touches them.

## Honest limitations

- **Gym type is a coarse proxy for equipment.** Five tiers, no item-level checklist. The original
  spec left that list unwritten and it is deliberately deferred until there is an exercise
  database to validate it against — so "commercial gym" assumes a machine selection you may not
  actually have.
- **The seven strength benchmarks are self-reported.** Nothing verifies them.
- **Bodyfat is a self-estimated bracket**, not a measurement, and it is stored as a range for
  exactly that reason.
- **No weights or progression yet.** A plan says movements, sets, reps and how close to failure;
  picking loads and progressing them week to week is the session-logging feature's job, when it
  exists. Rules that need that history (work capacity, asymmetry correction) are out of scope
  until then.
- **Exercise choice is a judgment, not a calculation.** Ask twice and you may get two different
  weeks, both hitting the same allocation. The budget and the candidate pool are reproducible;
  what gets chosen from them is reasoned, and you can ask why.
- **Benchmark gates are name-pattern based.** "Can't do five pull-ups" removes exercises whose
  names match pull-up patterns; a dataset with unusual naming could slip past them.

## Evaluating the skills

Each skill carries its own test cases in `evals/`, in the shape the
[skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) loop
reads ([how it works](https://agentskills.io/skill-creation/evaluating-skills)):

- `evals/evals.json` — realistic prompts, what a good outcome looks like, and gradable
  assertions. Every case runs in a fresh clone; its `setup` lines say what to seed under
  `profile/` (and `datasets/`) from `evals/files/` first. The generation cases use the bundled
  fixture dataset, so they run offline.
- `evals/trigger_queries.json` — about twenty prompts labelled should / should-not trigger,
  near-misses included, for tuning the `description`.

Run outputs, grades and benchmarks land in a sibling `<skill>-workspace/iteration-N/`, which is
gitignored. `python scripts/validate-skills.py` checks the shape of both files; running the
loop itself needs an agent.

## Roadmap

- ~~Workout generation reading `profile.json` and the latest `programs/*.json`, writing under
  `profile/plans/`~~ — built, see `/generate`
- Item-level equipment selection, seeded by gym type
- Session logging and progression

## Layout

Both skills follow the [Agent Skills](https://agentskills.io/specification) layout: a thin
`SKILL.md`, `references/` for what the agent reads on demand, `assets/` for data files,
`scripts/` for code, `evals/` for the test cases.

```
skills/onboarding/SKILL.md                     the interview flow — vendor-neutral, pointers + gotchas
skills/onboarding/references/questions.yaml    the interview content
skills/onboarding/references/rules.md          validation, updating, echo-before-write rules
skills/onboarding/assets/schema/               the schema, machine-readable
skills/onboarding/assets/examples/             copy-to-start samples
skills/onboarding/scripts/volume.py            the volume algorithm
skills/onboarding/scripts/volume.config.json   every number the volume model uses
skills/onboarding/evals/                       test cases, trigger queries, fixtures
skills/generation/SKILL.md                     the generation flow — vendor-neutral, pointers + gotchas
skills/generation/references/rules.md          dataset cache, personal rules, choosing, echo-before-write
skills/generation/references/coaching.md       training-design rules — how to choose, and why
skills/generation/assets/datasets.json         dataset registry — all dataset-specific knowledge
skills/generation/assets/schema/               plan, selection and rules contracts, machine-readable
skills/generation/assets/examples/             copy-to-start samples
skills/generation/scripts/generate.py          the budget, the candidate pool, and the checks
skills/generation/scripts/generate.config.json every number the generator uses
skills/generation/evals/                       test cases, trigger queries, fixtures (offline dataset included)
.claude/skills/onboard/SKILL.md                thin wrapper so /onboard works in Claude Code
.claude/skills/generate/SKILL.md               thin wrapper so /generate works in Claude Code
scripts/validate-skills.py                     validates both skills against the spec and their own schemas
tests/skills/                                  offline test suite, plus opt-in agent tests
docs/schema.md                                 profile/program fields, and the "why"
docs/generation.md                             the generator's "why": descriptor, fit, cache
docs/onboarding-fields.md                      hand-editing guide for profile.json and programs
docs/generation-fields.md                      hand-editing guide for rules.md and plans
docs/onboarding.md                             the original hand-written spec, kept as-is
profile/                                       your data, gitignored
datasets/                                      cloned exercise datasets, gitignored cache
```

## License

MIT.
