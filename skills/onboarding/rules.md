# Onboarding rules

Everything from the interview that is not a question: how to find whose profile this is, how to
validate an answer, what to say before writing, how updates work, and what to do without Python.
`questions.yaml` holds the questions; this file holds the rules around them.

## Resolving a profile

Several people can share this repository, one directory each — `profiles/<slug>/`. Resolve which
profile is in play **before asking anything else**, and never guess:

- **A name was supplied** (the skill was run with a name, or someone said "update Sara's
  profile"). Slugify it (see below) and look for `profiles/<slug>/profile.json`. Not found → say
  so and offer to create it. Found → check `user.name` inside before using it. Same person → that
  is the profile. Different person (`sara` holding "Sarah") → do not open it and do not overwrite
  it; say whose profile that slug holds and ask whether they meant that person or a new one.
- **No name, no profiles exist** → this is a new profile; the interview asks for the name.
- **No name, exactly one profile exists** → confirm rather than assume: "This is Samy's profile —
  continuing as Samy?" Cheap to ask, and it stops a housemate silently overwriting someone.
- **No name, several profiles exist** → list them and ask who this is, with an option for someone
  new.

There is no default profile and no last-used memory, on purpose. Writing to the wrong person's
profile is the main hazard of supporting more than one, and it fails silently.

If a profile already exists and this is not explicitly an update, stop and ask what they want:
summarise it in two lines (program name and emoji, goal, days per week — read from the latest file
under `programs/`, see below) and offer **change a few fields** (go to
[Updating](#updating-an-existing-profile)) or **start over** (full re-interview, overwriting
`profile.json` and creating a new dated program file). Proceed only on an explicit answer.

### Slug rules

Lowercase, trim, spaces and underscores to hyphens, drop anything outside `a-z0-9-`, collapse
repeated hyphens, strip leading and trailing hyphens. `Anna-Maria` → `anna-maria`, `Jean Luc` →
`jean-luc`. If the result is empty, ask for something usable instead of inventing one.

**When creating a profile**, if the slug is already taken by a different person, suffix it —
`sam-2`, then `sam-3` if that is taken too — and say so out loud. Never merge two people into one
file. Checking this means reading the existing `profile.json` to compare `user.name`; reading
another profile is fine, writing to one is not.

## Finding the latest program

`profiles/<slug>/programs/` holds one file per training block, named `program-YYYY-MM-DD.json`.
The **latest** program is the one whose filename sorts highest. A second run on the same calendar
day does not overwrite the first — suffix it `program-YYYY-MM-DD-2.json`, then `-3` if that is
also taken.

## Before writing

Show a compact summary before a single byte is written: name, age, height and weight in their
units, bodyfat bracket, gym type, goal, days × session length, split, deload, and how many of the
seven benchmarks they cleared. Age is computed from date of birth for display only and is never
stored — if only a birth year is known, show it as approximate ("about 32").

**Name the exact paths about to be written** — both `profiles/<slug>/profile.json` and
`profiles/<slug>/programs/program-<date>.json`.

Then say in plain English what follows from the notable answers:

- Gym type — "Garage gym, so the plan will stick to barbell, dumbbell and bodyweight work."
- Split and days — "Full body five days a week is a lot of full-body sessions; upper/lower may fit
  better. Keep full body?"
- Benchmarks — "You cleared 2 of 7, so the plan will start you on assisted or machine versions of
  the pressing and pulling patterns."

Let them veto anything before writing. If they change an answer, update the summary and confirm
again. **If they change units at this point, convert the measurements** (see
[Unit conversion](#unit-conversion) below) — do not relabel the numbers.

If they abandon the interview here or earlier, write nothing at all. A partial profile is worse
than no profile.

## Writing the files

Create `profiles/<slug>/` and `profiles/<slug>/programs/` if they do not exist. Write both files
shaped exactly by `schema/profile.schema.json` and `schema/program.schema.json` — key order
matters for readability even though the schema does not enforce it.

- `profile.json`: `$schema_version`, `created_at`, `updated_at` (both the current UTC time as
  `YYYY-MM-DDTHH:MM:SSZ` on a first write), `user`, `units`, `basics`, `experience`, `gym`,
  `strength_benchmarks`.
- `programs/program-<date>.json`: `$schema_version`, `created_at` (current UTC time),
  `profile_slug`, `program`. Leave `volume` absent or `null` — filling it is the next step, not
  this one.

Then run the volume step (`SKILL.md` step 5). Whether or not it succeeds, tell the person where
both files went, and that the workout-generation skill will use the program answers as defaults
they can change per cycle without redoing this interview.

## No Python

If the environment cannot run `skills/onboarding/scripts/volume.py` (no interpreter, no shell
access, sandboxed), do not hand-compute the volume model — the arithmetic is not something to
approximate from memory, and a wrong number is worse than a missing one. Instead:

1. Write `profile.json` and the program file exactly as above, with `volume` left `null`.
2. Tell the person plainly that the volume block could not be computed here, and give them the
   exact command to run it themselves later:
   `python skills/onboarding/scripts/volume.py --profile profiles/<slug>/profile.json --write profiles/<slug>/programs/program-<date>.json`
3. Do not block on this. A program file with `volume: null` is schema-valid and usable.

## Updating an existing profile

Resolve the profile first, exactly as in [Resolving a profile](#resolving-a-profile). Then ask
only about what they named — "change my weight to 82" needs no questions at all, just a
confirmation. If the request is vague ("update my profile"), offer a group picker — Basics · Gym ·
Program · Benchmarks — and re-run only that batch. This is never a full re-interview.

Fields from `questions.yaml` with `scope: profile` live in `profile.json`; fields with
`scope: program` live in a program file. **A change to any `scope: program` field always creates a
new dated program file** (see [Finding the latest program](#finding-the-latest-program)) rather
than editing the old one — a program answer is a per-cycle default, and the old cycle's file stays
as a record. A change to a `scope: profile` field edits `profile.json` in place.

Parse the existing file, change only what was asked for, and write the whole thing back in the
structure and key order the schema implies — do not patch the text in place. Every field that was
not changed keeps its exact value, including `profile.json`'s `created_at`. Bump `updated_at` on
`profile.json`. Three rules for fields that interact:

- **Changing `units` converts the measurements, it does not relabel them.** See
  [Unit conversion](#unit-conversion).
- **Changing `date_of_birth` touches nothing else** — age is derived at read time, never stored.
- **Changing the name re-slugs the directory.** Move the whole directory, not just
  `profile.json` — it also holds `programs/` and, eventually, `plans/`, and copying one file out
  before deleting the rest destroys the others. Rename `profiles/<old-slug>/` to
  `profiles/<new-slug>/`, then update `user.name` and `user.slug` inside the file. If the
  directory cannot be moved, leave it untouched and say plainly that the rename did not happen —
  never delete the old one first.

## Validation

- **Plausible ranges.** Height 120-230 cm (47-91 in), weight 35-250 kg (77-550 lb), birth year
  1920-2015, days per week 3-7. Check against whichever unit they answered in; the bounds are
  generous enough that rounding at the edges does not matter. Anything outside these is a typo
  until confirmed — ask again. Never silently clamp a value and never silently store an
  implausible one.
- **Never invent an answer.** If someone skips a question or answers ambiguously, ask again. Do
  not fill in a reasonable-sounding height, a default gym type, or a benchmark result. Exactly two
  auto-fills are permitted: `pullups_5` from `pullups_10`, and a program name or emoji default
  that was explicitly offered and accepted.
- **Bodyfat must be one of the nine bracket strings** in `questions.yaml`'s `bodyfat` entry. Not a
  number, not an invented range.
- **Echoing before writing is mandatory**, including both target paths. No first-pass write
  without the person seeing the summary.
- **Write only to `profiles/<slug>/profile.json`** and `profiles/<slug>/programs/program-<date>.json`.
  Never to `docs/`, never to `skills/`, never to another person's directory. Never modify anything
  under `skills/onboarding/examples/` — those are the shipped schema samples.

## Unit conversion

Used when `units` is changed on an existing profile. Convert the underlying measurement — do not
relabel the number.

- 1 in = 2.54 cm exactly
- 1 lb = 0.45359237 kg exactly

Round to one decimal. 178 cm becomes 70.1 in, not 178 in.

## What the generation skill reads

A future workout-generation skill consumes these files. It will:

- **Resolve a profile the same way** this skill does — same name argument, same
  ask-when-ambiguous rule, same slug derivation.
- **Read `profile.json` without asking:** `user.name`, `basics.*` (deriving age from
  `date_of_birth`), `experience.*`, `gym.type`, `strength_benchmarks.*`.
- **Read the latest `programs/program-*.json` and re-confirm in one pre-filled batch:**
  `program.primary_goal`, `program.days_per_week`, `program.session_minutes`, `program.split`,
  `program.deload`. Keeping all of them is one click.
- **Never write to `profile.json`.** If any `scope: profile` field needs to change, it points the
  person at this skill's update path instead of doing it itself.
- **Write its own output under `profiles/<slug>/plans/`** — never under `programs/`, which belongs
  to this skill's answers.
- **Fail loudly when no profile exists**, telling the person to run onboarding first rather than
  interviewing them itself.
