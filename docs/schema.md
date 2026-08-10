# Profile and program schema — rationale

The machine-readable contracts are
[`skills/onboarding/schema/profile.schema.json`](../skills/onboarding/schema/profile.schema.json)
and
[`skills/onboarding/schema/program.schema.json`](../skills/onboarding/schema/program.schema.json),
with [`skills/onboarding/examples/`](../skills/onboarding/examples/) holding a filled-in sample of
each. When this document and a schema disagree, the schema wins and this document is the bug. For
"what do I literally type in this field", see
[`skills/onboarding/FIELDS.md`](../skills/onboarding/FIELDS.md) instead — this file is the *why*.

[`onboarding.md`](onboarding.md) is the original hand-written spec and is kept as-is for
provenance, typos included.

---

## Storage layout

```
profile/
├── profile.json
├── programs/
│   ├── program-2026-08-06.json
│   └── program-2026-11-02.json
├── plans/
└── rules.json
```

**One repository holds one profile.** The person's name is stored inside `profile.json` as a
display label, and nothing on disk is named after it — so changing the name is an ordinary field
edit with no directory move behind it.

`profile.json` is written once and updated in place. `programs/` holds one file per training
block — every re-run of the program questions adds a new dated file rather than overwriting the
last one, so the answers given for last summer's cutting block are not silently lost when a bulk
is set up. The **latest** program is whichever filename sorts highest; a same-day re-run suffixes
`-2`.

`profile/plans/` is the workout-generation skill's output — never written by onboarding, and
named differently from `programs/` on purpose so the two kinds of file (*answers* vs. *generated
output*) are never confused by directory alone.

### Why one profile and not several

The safety property it existed to protect — never silently overwrite a profile — is kept, and now
sits in `skills/onboarding/rules.md` § If a profile already exists.

---

## Why the schema is split this way

**Why two files instead of one.** `profile.json` is who someone is: body stats, experience, where
they train. `programs/*.json` is what they want this cycle: goal, days, split. The first is stable
across months; the second is expected to change every training block. Splitting them means a new
cycle's answers never require re-touching, and can never accidentally overwrite, the first —
and a directory listing under `programs/` is a free history, with no `history` array to maintain
by hand.

**Why `program` answers are stored at all, given they're not commitments.** They are defaults the
generation skill re-confirms, not frozen settings. The point is that a returning person clicks
"same as last time" instead of answering the program questions again from scratch — storing them
is what makes that one click instead of five.

**Why `volume` is optional, and lives inside the program file rather than the profile.** It is a
computed function of the program answers plus a handful of profile fields — recomputable at any
time from the two source files, so it is not authoritative anywhere. Making it optional (absent or
`null` is valid) means a hand-filled profile/program pair is usable immediately, before anyone
runs `scripts/volume.py` — the "no interview" path in the README does not require Python as a
prerequisite for producing a valid pair of files, only for producing one with numbers filled in.

**Why age is never stored, only `date_of_birth`.** A stored age is correct on the day it is
written and wrong forever after: a profile saved in 2026 saying `age: 31` is read in 2028 and
silently plans for a 31-year-old. The derivation is a subtraction, so there is no scenario where
the stored value beats the computed one. If only a birth year is known,
`current_year - birth_year` is accurate to ±1, which does not matter for training.

**Why bodyfat is a bracket string and `session_minutes` is a range string, not numbers.** Storing
`15` for bodyfat or `75` for session length would assert a precision the person never gave —
nobody knows their bodyfat to the percent, and "60-90 minutes" is the actual answer, not an
invented midpoint. The bracket-to-midpoint and range-to-exercise-count mappings live in
`scripts/volume.config.json` (machine form) and the tables below (prose form) — the consumer's
job, not the schema's.

**Why measurements keep the user's own unit** rather than normalising to metric on disk.
Round-tripping a conversion on every update introduces float drift, and shows people numbers they
do not recognise when they open their own file. The unit travels on the value, so no consumer can
misread it.

**Why there is no `derived` block on disk.** An earlier version of this schema kept an
all-`null` `derived` object as documentation of what a consumer computes. That job is now done by
`volume.py`'s actual output plus this document's tables — a null placeholder added nothing a
comment couldn't, and namespaced the four values away from where they're actually used
(`volume.age`, `volume.bodyfat_midpoint`, `volume.equipment_tier`, `volume.benchmarks_cleared`
inside the program file, next to the numbers they feed).

**Why v1 models equipment as gym type only.** There is no item-level equipment checklist. The
original spec left that list unwritten and it is deliberately deferred until there is an exercise
database to validate it against — so "commercial gym" assumes a machine selection a given person
may not actually have. No item-level checklist without a `$schema_version` bump.

**Why `strength_benchmarks` is unconditional on `experience.lifting`, and why `pullups_10` implies
`pullups_5`.** The benchmarks are self-reported and used to gate exercise selection (assisted vs.
unassisted variants), not to recompute volume — see [Volume model](#volume-model). Normalising the
pull-up nesting at collection time means a stored profile is always internally consistent and
neither key is ever missing, rather than pushing that check onto every consumer.

---

## `profile.json`

### Top-level fields

| Field | Type | Rule |
|---|---|---|
| `$schema_version` | string | `"1.0"`. Bump the major on any breaking key change. Consumers must refuse an unknown major rather than guessing. |
| `created_at` | string | ISO 8601 UTC, `YYYY-MM-DDTHH:MM:SSZ`. Set once, never rewritten. |
| `updated_at` | string | Same format. Bumped on every write. |
| `user.name` | string | Verbatim as the person typed it, including case and accents. A display label only — nothing on disk is named after it. |
| `units` | enum | `metric` \| `imperial`. A display preference for everything, which is why it is top-level rather than nested under a measurement. |

### `basics`

| Field | Type | Rule |
|---|---|---|
| `sex` | enum | `male` \| `female`. Unused by v1 math; it exists because bodyfat brackets read differently by sex. |
| `date_of_birth` | string | `YYYY-MM-DD`, or bare `YYYY` if only a year was given. |
| `height` | object | `{ "value": <number>, "unit": "cm" \| "in" }`. Always an exact number, never a range. |
| `weight` | object | `{ "value": <number>, "unit": "kg" \| "lb" }`. Always an exact number, never a range. |
| `bodyfat_bracket` | enum | One of `3-4`, `5-7`, `8-12`, `13-17`, `18-23`, `24-29`, `30-34`, `35-39`, `40+`. A string, not a number. |

### `experience`

| Field | Type | Rule |
|---|---|---|
| `lifting` | enum | `none` \| `beginner` \| `intermediate` \| `advanced` |
| `cardio` | enum | Same four values. |

Bands: beginner is under 1 year, intermediate 1-4 years, advanced over 4 years.

### `gym`

| Field | Type | Rule |
|---|---|---|
| `type` | enum | `everything_gym` \| `commercial_gym` \| `warehouse_gym` \| `local_gym` \| `garage_gym` |
| `notes` | string \| null | Free text for volunteered extras ("I also have a cable machine"). Never a structured list in v1. |

#### Gym type → equipment tier

Consumed as `volume.equipment_tier`. Kept here rather than in the profile so the tiering can be
revised without rewriting anyone's saved data. This value rides along in `volume.py`'s output
unused by the arithmetic in v1 — see [Volume model](#volume-model) — reserved for a future
exercise-selection step.

| Type | Tier | Means |
|---|---|---|
| `everything_gym` | 4 | Full commercial selection plus specialty machines and bars |
| `commercial_gym` | 3 | Full machine and free-weight selection |
| `warehouse_gym` | 3 | Strength-focused: full barbell and racks, fewer machines |
| `local_gym` | 2 | Basic barbell, dumbbells, a few machines |
| `garage_gym` | 1 | Barbell, dumbbells, bodyweight. No machines. |

### `strength_benchmarks`

Seven booleans. **All seven keys are always present** — a consumer never has to distinguish
"absent" from "false".

| Field | Question |
|---|---|
| `pullups_5` | 5+ strict, unassisted pull-ups or chin-ups |
| `pullups_10` | 10+ strict, unassisted pull-ups or chin-ups |
| `dips_10` | 10+ bodyweight dips |
| `pushups_15` | 15+ strict bodyweight push-ups |
| `bench_press_10` | Barbell bench press for 10 reps |
| `incline_press_10` | Barbell incline press for 10 reps |
| `overhead_press_10` | Barbell overhead press for 10 reps |

These are self-reported and unverified. They exist to gate exercise *selection* — someone who
clears none gets assisted and machine variants of the pulling and pressing patterns — which is a
future generation-skill concern, not the volume model's.

---

## `programs/program-YYYY-MM-DD.json`

| Field | Type | Rule |
|---|---|---|
| `$schema_version` | string | `"1.0"`. |
| `created_at` | string | ISO 8601 UTC. When *this program file* was written — not the profile's `created_at`. |
| `program` | object | See below. |
| `volume` | object \| null | Computed by `scripts/volume.py`. Absent or `null` is a valid file — see [Volume model](#volume-model). |

### `program`

| Field | Type | Rule |
|---|---|---|
| `name` | string | Free text, 1-60 characters. |
| `emoji` | string | A single emoji. |
| `primary_goal` | enum | `hypertrophy` \| `strength` \| `both` |
| `days_per_week` | integer | 3-7 |
| `session_minutes` | enum | `up_to_20` \| `20-40` \| `40-60` \| `60-90` \| `90-120` \| `over_120` |
| `split` | enum | `full_body` \| `upper_lower` |
| `deload` | boolean | Whether the program ends with a lighter recovery week. |

**Why `session_minutes` is a string range, not a number of minutes.** The person answered a range;
storing `75` would invent a number they never gave. The range-to-exercise-count mapping is a
policy call belonging to the volume model, not a fact about the user:

| `session_minutes` | Exercises per session |
|---|---|
| `up_to_20` | 3 |
| `20-40` | 4 |
| `40-60` | 6 |
| `60-90` | 8 |
| `90-120` | 10 |
| `over_120` | 12 |

### Bodyfat bracket → midpoint

Consumed as `volume.bodyfat_midpoint`, rides along unused by v1's arithmetic — reserved the same
way as `equipment_tier`.

| Bracket | Midpoint | Bracket | Midpoint |
|---|---|---|---|
| `3-4` | 3.5 | `24-29` | 26.5 |
| `5-7` | 6 | `30-34` | 32 |
| `8-12` | 10 | `35-39` | 37 |
| `13-17` | 15 | `40+` | 42 |
| `18-23` | 20.5 | | |

`40+` is open-ended; 42 is a working stand-in, not a measurement.

---

## Volume model

`skills/onboarding/scripts/volume.py` computes `volume`, a weekly per-muscle set allocation, from
`program` plus a handful of `profile.json` fields. The algorithm lives in that file; every number
it uses lives in `skills/onboarding/scripts/volume.config.json` next to it, so retuning the model
never touches Python, `SKILL.md`, or `CLAUDE.md`.

**Five inputs drive the math**: `experience.lifting`, `primary_goal`, `days_per_week`,
`session_minutes`, `split`. Four values ride along computed but unused by v1's arithmetic, so two
future consumers cannot disagree about how to compute them: `age`, `bodyfat_midpoint`,
`equipment_tier`, `benchmarks_cleared`. `deload`, `experience.cardio`, and the benchmark booleans
do not affect volume in v1 — benchmarks gate exercise *selection*, a future generation-skill
concern.

```
C     = days * exercises_per_session[session] * sets_per_exercise[goal]     # weekly capacity
w[m]  = base_weights[m] * goal_multipliers[goal][m] * split_multipliers[split][m]
T     = target_weekly_sets_per_muscle[lifting] * sum(w)
s     = min(C / T, max_scale_factor)                                        # 1.5 caps degenerate inputs
total = C if C/T <= max_scale_factor else round(T * max_scale_factor)
alloc = hamilton(w, total)                                                  # largest-remainder rounding, proportional to w
```

Hamilton (largest-remainder) apportionment provably sums to `total` exactly; remainder ties break
by canonical muscle order (`chest, back, shoulders, biceps, triceps, quads, hamstrings, glutes,
calves, core`), so the output is byte-identical across platforms for the same inputs.

Starting values, grounded in the commonly cited ~10-20 hard-sets-per-muscle-per-week band, with
`none` deliberately below it — see `volume.config.json` for the exact numbers in force:

| `experience.lifting` | target sets/muscle | | `primary_goal` | sets/exercise |
|---|---|---|---|---|
| `none` / `beginner` / `intermediate` / `advanced` | 8 / 10 / 14 / 18 | | `hypertrophy` · `both` / `strength` | 3 / 4 |

Base priority weights favor the largest muscle groups (`back` 1.2, `quads` 1.1) down to the
smallest (`calves`, `core` 0.6). Goal multipliers in `volume.config.json` push volume toward
compound-dominant muscles for `strength` and toward isolation-dominant muscles for `hypertrophy`
(`both` is flat `1.0` everywhere). Split multipliers squeeze isolation work on `full_body` (harder
to fit five muscle groups' isolation work into one session) and raise it on `upper_lower` (more
session slots to spend on it).

### Warnings

`volume.warnings` is a list of zero or more of:

| Warning | Meaning |
|---|---|
| `capacity_below_mev` | The smallest per-muscle allocation fell under `mev_sets_per_muscle` — days × session length is tight for the chosen goal. |
| `capacity_exceeds_target` | `max_scale_factor` capped the allocation; `unallocated_sets` is nonzero. More session capacity than the model will assign. |
| `untrained:<muscle>` | None of that muscle's mapped `strength_benchmarks` are cleared (`muscle_benchmarks` in the config) — informational, does not change the allocation. |
| `full_body_high_frequency` | `split` is `full_body` at `full_body_high_frequency_days` or more days a week — a lot of full-body sessions; `upper_lower` may fit better. |

### CLI

Python 3.9+, stdlib only. Prints the computed `volume` object as JSON to stdout by default;
`--write <program.json>` merges it into an existing program file in place, reading
`goal`/`days`/`session`/`split` from that file's own `program` object when the CLI flags are
omitted. Flags are enum tokens and integers only, never JSON on the command line — that is where
cross-shell quoting breaks. Deterministic given `--today`. Exit `0` success, `2` usage error, `3`
input error — an unknown enum is refused, never defaulted. `--self-test` runs two pinned worked
cases plus all 720 `(lifting × goal × days × session × split)` enum combinations, checking that
each allocation sums exactly to its `weekly_sets_allocated`.

---

## Validation ranges

Enforced when answers are collected. A value outside these is treated as a typo until confirmed —
re-asked, never silently clamped and never silently stored.

| Field | Accepted |
|---|---|
| Height | 120-230 cm / 47-91 in |
| Weight | 35-250 kg / 77-550 lb |
| Birth year | 1920-2015 |
| Days per week | 3-7 |

---

## Changing the schema

`skills/onboarding/schema/profile.schema.json` and `skills/onboarding/schema/program.schema.json`
are the schema of record. Any field change updates the relevant schema, its example under
`skills/onboarding/examples/`, `questions.yaml` or `volume.config.json` as appropriate, and this
document, in the same commit. A breaking change bumps `$schema_version` — once there is released
data to break. Nothing has shipped yet, so pre-release breaking changes (such as dropping
multi-person support, which removed `user.slug` and `profile_slug`) edit the schemas in place and
everything stays at `"1.0"`.
