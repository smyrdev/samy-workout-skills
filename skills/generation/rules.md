# Generation rules

Everything around the generator that is not the flow itself: what the inputs must look like, how
the dataset cache works, what to say before writing, and what this skill must never do.
`SKILL.md` holds the flow; this file holds the rules the flow points at.

## Program answers and volume

The inputs are `profile/profile.json` and the **latest** file under `profile/programs/`
(latest = filename sorts highest — the same rule onboarding uses).
The program file's `volume` block is the contract between the two skills: `volume.py` (onboarding)
computes how many weekly sets each muscle group gets; this skill decides which exercises deliver
them. **Targets are never computed or adjusted here** — one owner per number.

If the program file has no volume block (or `volume: null`), do not estimate one. Run the
onboarding volume step first:

```
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-<date>.json
```

The generator itself refuses to run without it, with this same instruction.

## Personal rules

`profile/rules.json` is the person's own, hand-written file — excluded exercises or equipment,
muscle groups to focus or drop, exercise ordering. Shaped by
`schema/rules.schema.json`, explained field-by-field in `FIELDS.md`, sample at
`examples/rules.example.json`.

- **This skill reads it and never writes it.** If the person states a lasting preference during
  the review loop ("never give me burpees"), offer the exact snippet to paste into their
  `rules.json` — creating or editing that file is their act, not the skill's.
- Absent file → the defaults in `scripts/generate.config.json` (`default_rules`) apply. Present
  file → its sections override the defaults key-by-key; anything it does not mention keeps the
  default.
- A one-off request ("no squats this cycle") is a `--rules` file passed for that run only — it
  does not have to live at `profile/rules.json` to be honored.

Unknown names in the rules file (a typo, an exercise the dataset does not have) come back as
warnings in the plan — surface them to the person; never silently drop a rule.

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
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --write profile/plans/plan-<today>.json \
  --write-md profile/plans/plan-<today>.md
```

Add `--rules profile/rules.json` when that file exists. Plan filenames use today's date;
if the name is taken (a same-day re-run), suffix `-2`, then `-3` — the generator refuses to
overwrite an existing plan, and so does this skill. Old plans are records; they are never edited
and never deleted by this skill.

Everything tunable — session ordering defaults, movement-group variety, rep ranges, the deload
multiplier — lives in `scripts/generate.config.json`, never in the script and never in prose.

## No Python

If the environment cannot run `scripts/generate.py` (no interpreter, no shell, sandboxed), do not
imitate the algorithm by hand — fitting a thousand-exercise dataset to per-muscle set targets is
not something to approximate from memory. Write nothing, tell the person plainly, and give them
the exact command from [Running the generator](#running-the-generator) to run themselves. A
missing plan is recoverable; a plausible-looking wrong one is not.

## Before writing

Show, before any file lands:

- The **planned-versus-allocated table** — per muscle group, what the volume model allocated and
  what the fitted week actually delivers.
- The **week itself** — each day's exercises with sets and reps.
- **Every warning**, in plain English: a short muscle group ("the available equipment cannot
  reach the hamstrings allocation — closest is 6 of 9 sets"), an excluded name that matched
  nothing, an unplaceable must-include.
- The **exact paths** about to be written.

Let the person veto or adjust. An exercise swap is a rules change and a re-run — a `--rules` file
for one cycle, or their `rules.json` for always — so the volume arithmetic stays true; never
hand-edit an exercise into the generator's output. If they abandon here, write nothing.

## What this skill never does

- Never writes to `profile.json`, to `programs/`, to `rules.json`, or to `datasets.json`. Its
  entire writable surface is `profile/plans/`.
- Never re-interviews. Profile changes go through onboarding.
- Never computes or adjusts volume targets — that is `volume.py`'s job alone.
- Never commits the dataset cache or anything under `profile/`.
- Never hides a shortfall. If the targets cannot be met with the available equipment and rules,
  the plan says so in `warnings` and the person hears it in the echo step.
