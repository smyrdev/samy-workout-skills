# Generation rules

Everything around the generator that is not the flow itself: what the inputs must look like, how
the dataset cache works, what to say before writing, and what this skill must never do.
`SKILL.md` holds the flow; this file holds the rules the flow points at.

## Program answers and volume

The inputs are the person's `profiles/<slug>/profile.json` and the **latest** file under
`profiles/<slug>/programs/` (latest = filename sorts highest — the same rule onboarding uses).
The program file's `volume` block is the contract between the two skills: `volume.py` (onboarding)
computes how many weekly sets each muscle group gets; this skill decides which exercises deliver
them. **Targets are never computed or adjusted here** — one owner per number.

If the program file has no volume block (or `volume: null`), do not estimate one. Run the
onboarding volume step first:

```
python skills/onboarding/scripts/volume.py --profile profiles/<slug>/profile.json \
  --write profiles/<slug>/programs/program-<date>.json
```

The generator itself refuses to run without it, with this same instruction.

## Personal rules

`profiles/<slug>/rules.json` is the person's own, hand-written file — excluded exercises or
equipment, muscle groups to focus or drop, exercise ordering. Shaped by
`schema/rules.schema.json`, explained field-by-field in `FIELDS.md`, sample at
`examples/rules.example.json`.

- **This skill reads it and never writes it.** If the person states a lasting preference during
  the review loop ("never give me burpees"), offer the exact snippet to paste into their
  `rules.json` — creating or editing that file is their act, not the skill's.
- Absent file → the defaults in `scripts/generate.config.json` (`default_rules`) apply. Present
  file → its sections override the defaults key-by-key; anything it does not mention keeps the
  default.
- A one-off request ("no squats this cycle") is a `--rules` file passed for that run only — it
  does not have to live at `profiles/<slug>/rules.json` to be honored.

Unknown names in the rules file (a typo, an exercise the dataset does not have, a muscle group
that is not one of the ten) come back as warnings in the plan — surface them to the person; never
silently drop a rule. A misspelled **section** name is different and worse: it would disable every
rule inside it, so the generator refuses the file outright rather than warning. Exercise and
equipment names are matched case-insensitively.

The `notes` section is different in kind from the rest: freeform strings the fitting algorithm
ignores entirely. It is coaching guidance for the [review step](#reviewing-the-plan) — "prefer
supersets when short on time", "keep the first exercise heavy". The generator only echoes it into
the plan's `rules_applied` so the plan records what guidance was in force.

## Dataset cache

Datasets are described in `datasets.json` — repository, ref, file paths, field names, equipment
tiers, muscle mapping. The data itself is **never committed to this repository**. It lives in a
gitignored cache at `datasets/<name>/`, one directory per descriptor entry:

- Cache present → use it. Offer (do not force) a pull when the person asks for fresh data.
- Cache absent → clone it: `git clone --depth 1 --branch <ref> <repo> datasets/<name>`.
- No cache and no way to clone (offline, no git) → **stop and say so.** Never fabricate
  exercises, never generate from memory of what the dataset probably contains.

The generator records the cache's commit hash in the plan, so a plan stays reproducible even
though the descriptor's ref usually tracks a moving branch.

To use a different dataset: add an entry to `datasets.json` (every field the current entry has —
the mapping tables are what make the generator dataset-agnostic) and pass its name. The
generator refuses a dataset whose vocabulary is not fully mapped rather than guessing.

## Running the generator

```
python skills/generation/scripts/generate.py \
  --profile profiles/<slug>/profile.json \
  --program profiles/<slug>/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --write profiles/<slug>/plans/plan-<today>.json \
  --write-md profiles/<slug>/plans/plan-<today>.md
```

Add `--rules profiles/<slug>/rules.json` when that file exists. Plan filenames use today's date;
if the name is taken (a same-day re-run), suffix `-2`, then `-3` — the generator refuses to
overwrite an existing plan, and so does this skill. Old plans are records; they are never edited
and never deleted by this skill.

Everything tunable — the ordering vocabulary and its default, movement-group variety, rep ranges,
the deload multiplier, the balance tolerance — lives in `scripts/generate.config.json`, never in
the script and never in prose.

## No Python

If the environment cannot run `scripts/generate.py` (no interpreter, no shell, sandboxed), do not
imitate the algorithm by hand — fitting a thousand-exercise dataset to per-muscle set targets is
not something to approximate from memory. Write nothing, tell the person plainly, and give them
the exact command from [Running the generator](#running-the-generator) to run themselves. A
missing plan is recoverable; a plausible-looking wrong one is not.

## Reviewing the plan

The fitter's output is a draft, not a verdict. After it runs, review the week as a coach — against
the rules file's `notes` and whatever the person asked this cycle — and revise it before the echo
step. Every change is one plain-English line in the plan's `revisions` array; an untouched plan
carries no `revisions` at all, and that is a fine outcome.

May revise:

* **Reorder** exercises within a day
* **Swap** an exercise for another from the dataset — read the replacement's record and carry its
  real muscle/volume map into the plan; never invent coefficients. A swap must satisfy everything
  the fitter enforced: equipment tier, benchmark gates, rules exclusions
* **Adjust sets** on an exercise — deload sets scale with it, same ×0.5 floor-1 rule
* **Pair supersets or compound sets** within a day — recorded in the session's `supersets` as id
  pairs, both ids present in that session
* **Move an exercise between two days of the same focus** (upper→upper, lower→lower)

Never touches:

* Per-muscle targets — the `allocated` numbers are `volume.py`'s alone
* Equipment tier, benchmark gates, the split skeleton (which days exist, their focus)
* `profile.json`, `programs/`, `rules.json` — same ownership as everywhere else

If a revision shifts a group's delivered volume meaningfully, say so in the echo step — plainly,
with the group named. Never revise silently, never revise without recording, and never present a
revised week as the fitter's output.

## Before writing

Show, before any file lands:

- The **volume table** — per muscle group: allocated sets, direct sets delivered, and `balance`.
  Read balance, not the raw gap: the two models count differently, so direct sets exceed the
  allocation for every group and only the balance ratio says whether the week is proportional.
- The **week itself, as revised** — each day's exercises with sets and reps, deload sets if there
  is one, and each revision with its reason.
- **Every warning**, in plain English: a group over or under its share ("core is getting about
  1.7× its share, because nearly every compound hits it"), a group the equipment cannot reach at
  all, a day the variety caps left short, an excluded name that matched nothing, an unplaceable
  must-include, anything the volume model itself flagged.
- The **exact paths** about to be written.

Let the person veto or adjust. A swap asked for here is one more recorded revision, held to the
same constraints as the [review step](#reviewing-the-plan); a preference meant to last is a
`rules.json` snippet to offer — that file is theirs to edit, not this skill's. If they abandon
here, write nothing.

## What this skill never does

- Never writes to `profile.json`, to `programs/`, to `rules.json`, to `datasets.json`, or to
  another person's directory. Its entire writable surface is `profiles/<slug>/plans/`.
- Never re-interviews. Profile changes go through onboarding.
- Never computes or adjusts volume targets — that is `volume.py`'s job alone.
- Never revises without recording. Every departure from the fitter's output is a `revisions` line;
  a plan with no `revisions` **is** the fitter's output, byte for byte.
- Never commits the dataset cache or anything under `profiles/`.
- Never hides a mismatch in either direction. If the targets cannot be met with the available
  equipment and rules, or a group ends up with well over or under its share of the week, the plan
  says so in `warnings` and the person hears it in the echo step.
