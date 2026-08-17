# Onboarding rules

What the flow points at that is not a question: the overwrite guard, what to say before writing,
how updates work, what to do without Python. `questions.yaml` holds the questions and their own
validation notes; this file holds the rules around them.

## If a profile already exists

One repository holds one profile, at `profile/`. Check whether `profile/profile.json` exists
**before asking anything else** — a fresh interview overwrites it, and that failure is silent.

- **No profile** → run the interview.
- **Profile exists, explicitly an update** → [Updating](#updating-an-existing-profile).
- **Profile exists, not explicitly an update** → stop and ask. Summarise it in two lines —
  `user.name`, experience and gym type from `profile.json`; program name, emoji, goal and days
  per week from the latest file under `programs/` (or say there is none and offer **set up a
  program**: only the `scope: program` questions). Then offer **change a few fields** →
  [Updating](#updating-an-existing-profile), or **start over** → full re-interview, overwriting
  `profile.json` and adding a new dated program file. Proceed only on an explicit answer — "set
  me up" from someone who already has a profile is ambiguous, not permission.

## Finding the latest program

`profile/programs/program-YYYY-MM-DD.json`, one file per training block. The **latest** is the
filename that sorts highest. A second run on the same day does not overwrite the first — suffix
`-2`, then `-3`.

## Before writing

Show a compact summary before a single byte is written: name, age (derived from date of birth for
display only, never stored — "about 32" if only a year is known), height and weight in their units,
bodyfat bracket, gym type, goal, days × session length, split, deload, benchmarks cleared out of
seven. **Name the exact paths about to be written** — `profile/profile.json` and
`profile/programs/program-<date>.json`. Add one plain-English line per notable consequence
(garage gym → barbell/dumbbell/bodyweight work; 2 of 7 benchmarks → assisted pressing and pulling
to start).

Let them veto anything. A changed answer updates the summary and is confirmed again; a changed
`units` converts the measurements — [Unit conversion](#unit-conversion) — never relabels them.
If they abandon here or earlier, write nothing.

## Writing the files

Create `profile/` and `profile/programs/` if needed. Write both files in the key order the schemas
list — `assets/schema/profile.schema.json`, `assets/schema/program.schema.json`. `created_at` and
`updated_at` are the current UTC time as `YYYY-MM-DDTHH:MM:SSZ`; the program file's `volume` is
left absent or `null` — the next step fills it. Afterwards, whether or not the volume step
succeeds, say where both files went and that the generation skill reads the program answers as
per-cycle defaults.

## No Python

If `skills/onboarding/scripts/volume.py` cannot run here (no interpreter, no shell, sandboxed), do
not hand-compute the volume model — a wrong number is worse than a missing one. Write the two files
with `volume` left `null` (schema-valid and usable), and give the person the exact command to run
later:

```
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-<date>.json
```

Do not block on this.

## Updating an existing profile

Confirm it is an update, as in [If a profile already exists](#if-a-profile-already-exists). Ask
only about what they named — "change my weight to 82" needs no questions, just a confirmation. A
vague "update my profile" gets a group picker — Basics · Gym · Program · Benchmarks — and only that
batch is re-run. This is never a full re-interview.

`scope: profile` fields (in `questions.yaml`) live in `profile.json` and are edited in place;
**any `scope: program` change creates a new dated program file** — see
[Finding the latest program](#finding-the-latest-program) — because a program answer is a
per-cycle default and the old file is the record of that cycle.

Parse, change only what was asked, write the whole file back in schema key order — never patch
the text. Unchanged fields keep their exact values, including `created_at`; bump `updated_at`.
Three fields interact:

- `units` → convert the measurements ([Unit conversion](#unit-conversion)), do not relabel.
- `date_of_birth` → touches nothing else; age is derived at read time.
- `user.name` → touches nothing else; it is a label, not a path.

## Validation

- **Plausible ranges.** Height 120-230 cm (47-91 in), weight 35-250 kg (77-550 lb), birth year
  1920-2015, days per week 3-7 — in whichever unit they answered. Outside → a typo until
  confirmed; ask again. Never silently clamp, never silently store.
- **Never invent an answer.** A skipped or ambiguous question is asked again. Two auto-fills only:
  `pullups_5` from `pullups_10`, and a program name or emoji default that was offered and accepted.
- **Echoing before writing is mandatory**, including both target paths.
- **Write only to `profile/profile.json` and `profile/programs/program-<date>.json`.** Never to
  `docs/`, `skills/`, or `profile/plans/` (generation's). Never modify
  `skills/onboarding/assets/examples/` — those are the shipped samples.

## Unit conversion

Convert the measurement, never relabel the number: 1 in = 2.54 cm exactly, 1 lb = 0.45359237 kg
exactly. Round to one decimal — 178 cm becomes 70.1 in, not 178 in.

## What the generation skill reads

`profile.json` without asking; the latest program file's `primary_goal`, `days_per_week`,
`session_minutes`, `split`, `deload` re-confirmed in one pre-filled batch. It writes only under
`profile/plans/` and sends every profile or program change back through this skill's update path.
Its own contract: `skills/generation/references/rules.md` § What this skill never does.
