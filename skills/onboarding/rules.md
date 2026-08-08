# Onboarding rules

`questions.yaml` holds the questions. This holds the rules around them.

## Resolving a profile

One directory per person — `profiles/<slug>/`. Resolve it before asking anything else. Never guess.

* Name supplied → slugify, look for `profiles/<slug>/profile.json`
  * missing → offer to create it
  * `user.name` matches → use it
  * `user.name` is someone else → say whose it is, ask which they meant. Do not open or overwrite
* No name, no profiles → new profile, the interview asks for the name
* No name, one profile → confirm it ("continuing as Samy?"), never assume
* No name, several → list them, ask, offer "someone new"
* Profile exists and this is not an update → summarise it in two lines (name, emoji, goal,
  days/week, from the latest program file) and ask: change a few fields
  ([Updating](#updating-an-existing-profile)) or start over. Only proceed on an explicit answer

No default profile, no last-used memory — writing to the wrong person fails silently.

### Slug rules

* Lowercase, trim, spaces and underscores → hyphens, drop anything outside `a-z0-9-`, collapse
  repeats, strip leading and trailing. `Jean Luc` → `jean-luc`
* Empty result → ask for something usable, never invent one
* Slug taken by someone else → suffix `-2`, then `-3`, and say so. Never merge two people
* Reading another `profile.json` to check that is fine. Writing to one is not

## Finding the latest program

* `programs/program-YYYY-MM-DD.json`, one per training block. Latest = highest-sorting filename
* Same day twice → `program-YYYY-MM-DD-2.json`, then `-3`. Never overwrite

## Before writing

* Summarise first: name, age, bodyfat, gym type, goal, days × session length, split, deload,
  benchmarks cleared out of seven
* Age is derived for display only, never stored. Birth year only → "about 32"
* Name both paths: `profiles/<slug>/profile.json` and `programs/program-<date>.json`
* Say what follows from the notable answers — garage gym → barbell, dumbbell and bodyweight only;
  full body five days → offer upper/lower; 2 of 7 benchmarks → assisted or machine variants
* They can veto anything. Changed answer → re-summarise, confirm again
* They walk away → write nothing. A partial profile is worse than none

## Writing the files

* Create `profiles/<slug>/` and `profiles/<slug>/programs/` if missing
* Shape both files by `schema/profile.schema.json` and `schema/program.schema.json`. Key order
  matters for readability, though the schema does not enforce it
* `profile.json`: `$schema_version`, `created_at`, `updated_at` (both current UTC,
  `YYYY-MM-DDTHH:MM:SSZ`), `user`, `basics`, `experience`, `gym`, `strength_benchmarks`
* `units`, `basics.sex`, `basics.height`, `basics.weight`, `experience.cardio`, `gym.notes` are
  allowed but unasked and unread — write one only if volunteered
* `programs/program-<date>.json`: `$schema_version`, `created_at`, `profile_slug`, `program`.
  `volume` stays `null` — the next step fills it
* Then run the volume step (`SKILL.md` step 5), and either way tell them where both files went and
  that generation reuses the program answers as per-cycle defaults

## No Python

* Cannot run `scripts/volume.py` here → do not hand-compute it. A wrong number is worse than a
  missing one
* Write both files with `volume: null` — schema-valid and usable. Do not block
* Give them the command:
  `python skills/onboarding/scripts/volume.py --profile profiles/<slug>/profile.json --write profiles/<slug>/programs/program-<date>.json`

## Updating an existing profile

* Resolve the profile first, as above
* Ask only about what they named. "Change my bodyfat to 18-23" is a confirmation, not a question
* Vague ask → group picker: Basics · Gym · Program · Benchmarks. Re-run that batch only. Never a
  full re-interview
* `scope: profile` → edits `profile.json` in place. `scope: program` → **always a new dated program
  file**, never an edit to the old one. The old cycle stays as a record
* Rewrite the whole file in schema key order, never patch text in place. Untouched fields keep
  their exact values, including `created_at`. Bump `updated_at`
* `date_of_birth` touches nothing else — age is derived at read time
* Name change re-slugs the directory: move all of `profiles/<old-slug>/`, not just `profile.json` —
  it also holds `programs/` and later `plans/`. Then update `user.name` and `user.slug`. If it
  cannot be moved, say the rename did not happen. Never delete the old one first

## Validation

* Birth year 1920-2015, days/week 3-7. Outside that is a typo until confirmed — ask again. Never
  clamp, never store it silently
* Never invent an answer. Skipped or ambiguous → ask again
* Two auto-fills only: `pullups_5` from `pullups_10`, and a program name or emoji default that was
  offered and accepted
* Bodyfat is one of the nine bracket strings in `questions.yaml` — not a number, not a new range
* Echoing before writing is mandatory, both paths included
* Write only to `profiles/<slug>/`. Never `docs/`, never `skills/`, never someone else's directory,
  never `examples/`

## What the generation skill reads

`skills/generation/` consumes these files. It:

* Resolves a profile exactly the same way
* Reads `strength_benchmarks.*` from `profile.json` without asking — everything else the volume
  model needs came through the program file's volume block
* Reads the latest program file and re-confirms goal, days, session, split and deload in one
  pre-filled batch
* Never writes to `profile.json` — it points at this skill's update path instead
* Writes only under `profiles/<slug>/plans/`, never `programs/`
* Fails loudly when no profile exists rather than interviewing anyone itself

## User
* This is a user rule.