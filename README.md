# samy-workout-skills

Two portable skills: **onboarding** interviews you once about your training situation and saves
it; **generation** turns that into a concrete week of exercises, fitted to a per-muscle weekly
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
exercise dataset into a local cache, fits exercises to your computed weekly per-muscle set
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
[`skills/onboarding/FIELDS.md`](skills/onboarding/FIELDS.md) as a guide, and validate.

```bash
mkdir -p profile/programs
cp skills/onboarding/examples/profile.example.json profile/profile.json
cp skills/onboarding/examples/program.example.json profile/programs/program-2026-08-06.json
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
Each set of an exercise adds its coefficients to your weekly per-muscle totals, and the generator
picks exercises until every muscle group's allocation is met — or tells you honestly which group
falls short with your equipment.

The dataset is cloned into a gitignored `datasets/` cache on first use. Everything the generator
knows about it — field names, equipment tiers, how its 22-muscle vocabulary maps onto the volume
model's 10 groups — lives in
[`skills/generation/datasets.json`](skills/generation/datasets.json). Point that file at a
different dataset and nothing else changes.

## Your rules

`profile/rules.json` is a hand-written file of standing preferences the generator reads
on every run: exercises or equipment to never use, muscle groups to focus or drop, how sessions
are ordered. Copy
[`skills/generation/examples/rules.example.json`](skills/generation/examples/rules.example.json)
and edit — [`skills/generation/FIELDS.md`](skills/generation/FIELDS.md) explains every field.
Typos are reported as warnings in the plan, never silently ignored.

## Where your data lives

`profile/` is gitignored in full. Your body stats are never committed, even by accident.

- `profile/profile.json` — who you are: body stats, experience, gym. Written once, updated in
  place when something about you changes.
- `profile/programs/program-<date>.json` — what you want this cycle: goal, days, split, and (once
  `volume.py` has run) a computed weekly per-muscle set allocation. One file per training block;
  the highest-dated filename is the current one.
- `profile/rules.json` — your standing generation preferences, written by you alone.
- `profile/plans/plan-<date>.json` + `.md` — generated plans, one dated pair per run, never
  overwritten. The `.md` is yours to scribble on.

The schema lives at
[`skills/onboarding/schema/profile.schema.json`](skills/onboarding/schema/profile.schema.json) and
[`skills/onboarding/schema/program.schema.json`](skills/onboarding/schema/program.schema.json),
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
- **No weights or progression yet.** A plan says movements, sets and rep ranges; picking loads
  and progressing them week to week is the session-logging feature's job, when it exists.
- **Benchmark gates are name-pattern based.** "Can't do five pull-ups" removes exercises whose
  names match pull-up patterns; a dataset with unusual naming could slip past them.

## Roadmap

- ~~Workout generation reading `profile.json` and the latest `programs/*.json`, writing under
  `profile/plans/`~~ — built, see `/generate`
- Item-level equipment selection, seeded by gym type
- Session logging and progression

## Layout

```
skills/onboarding/SKILL.md              the interview flow — vendor-neutral, pointers only
skills/onboarding/questions.yaml         the interview content
skills/onboarding/rules.md               validation, updating, echo-before-write rules
skills/onboarding/FIELDS.md              hand-editing guide
skills/onboarding/schema/                the schema, machine-readable
skills/onboarding/examples/              copy-to-start samples
skills/onboarding/scripts/volume.py      the volume algorithm
skills/onboarding/scripts/volume.config.json   every number the volume model uses
skills/generation/SKILL.md              the generation flow — vendor-neutral, pointers only
skills/generation/rules.md               dataset cache, personal rules, echo-before-write
skills/generation/FIELDS.md              hand-editing guide for rules.json and plans
skills/generation/datasets.json          dataset registry — all dataset-specific knowledge
skills/generation/schema/                plan and rules contracts, machine-readable
skills/generation/examples/              copy-to-start samples
skills/generation/scripts/generate.py    the fitting algorithm
skills/generation/scripts/generate.config.json   every number the generator uses
.claude/skills/onboard/SKILL.md          thin wrapper so /onboard works in Claude Code
.claude/skills/generate/SKILL.md         thin wrapper so /generate works in Claude Code
scripts/validate-skills.py               validates both skills against their own schemas
docs/schema.md                           profile/program fields, and the "why"
docs/generation.md                       the generator's "why": descriptor, fit, cache
docs/onboarding.md                       the original hand-written spec, kept as-is
profile/                                 your data, gitignored
datasets/                                cloned exercise datasets, gitignored cache
```

## License

MIT.
