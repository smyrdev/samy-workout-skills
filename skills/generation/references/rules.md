# Generation rules

What the flow points at that is not the flow itself: what the inputs must look like, how the
dataset cache works, how to choose from a brief, what to say before writing, what this skill never
does. `coaching.md` beside this file holds the training-design knowledge those choices are made
with.

## Program answers and volume

Inputs: `profile/profile.json` and the **latest** file under `profile/programs/`
(`skills/onboarding/references/rules.md` § Finding the latest program). Its `volume` block is the
contract between the two skills — `volume.py` decides how many weekly sets each muscle group gets,
this skill decides which exercises deliver them.
**Targets are never computed or adjusted here** — one owner per number.

No volume block, or `volume: null` → do not estimate one. Run onboarding's volume step first (the
generator refuses without it, with the same instruction):

```
python skills/onboarding/scripts/volume.py --profile profile/profile.json \
  --write profile/programs/program-<date>.json
```

## Personal rules

`profile/rules.md` is the person's own, hand-written file — exclusions, focus, ordering. It is
plain Markdown: `## Section` headings, one `- item` bullet per value, any other prose ignored as a
note to self. Explained in the repository's `docs/generation-fields.md`, sample at
`assets/examples/rules.example.md`; `assets/schema/rules.schema.json` describes what the generator
parses it into, not something anyone types.

- **This skill reads it and never writes it.** A lasting preference stated in the review loop
  ("never give me burpees") becomes a snippet offered for them to paste — creating or editing the
  file is their act. Offer that snippet as Markdown bullets under the right heading, never as JSON.
- Absent → `default_rules` in `scripts/generate.config.json`. Present → its sections override the
  defaults key-by-key. A heading with no bullets under it means "none", which is how a default is
  switched off.
- A one-off ("no squats this cycle") is a `--rules` file for that run only; it need not live at
  `profile/rules.md`.
- Unknown names (a typo, an exercise the dataset lacks) come back as plan warnings — surface them;
  never silently drop a rule.

## Dataset cache

`assets/datasets.json` describes each dataset — repository, ref, paths, field names, tiers, muscle
mapping. The data itself is **never committed to this repository**; it lives in the gitignored
`datasets/<name>/`.

- Cache present → use it; offer (do not force) a pull when fresh data is asked for.
- Cache absent → `git clone --depth 1 --branch <ref> <repo> datasets/<name>`.
- Neither possible (offline, no git) → **stop and say so.** Never fabricate exercises,
  never generate from memory of what the dataset probably contains.

The plan records the cache's commit, so it stays reproducible while the ref tracks a branch. A
different dataset is a new descriptor entry passed by name; the generator refuses one whose
vocabulary is not fully mapped.

## Running the generator

Three commands. The first asks what the week may contain; the second says what the chosen week
delivers, without writing; the third writes it.

```
python skills/generation/scripts/generate.py --brief \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name>
```

That prints the budget and the candidate pools, and writes nothing. Choose from it —
[Choosing from the brief](#choosing-from-the-brief) — then hand the choices back **without**
`--write`:

```
python skills/generation/scripts/generate.py \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --selection <selection>.json
```

This is the check. It composes the week, prints the plan JSON to stdout and, on stderr, the
allocated-versus-planned table with every warning. That table is what the echo step shows —
[Before writing](#before-writing) — and the planned column is the generator's number, never a hand tally:
indirect volume is discounted, and a coach's sum will disagree with the script's.
If a target is short or a choice looks wrong, change the selection and run the check again;
nothing has been written yet.

Only when the person has seen it and not vetoed, run the same command once more with the
outputs added:

```
python skills/generation/scripts/generate.py \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --selection <selection>.json \
  --write profile/plans/plan-<today>.json \
  --write-md profile/plans/plan-<today>.md
```

Add `--rules profile/rules.md` to all three when it exists. If today's filename is taken,
suffix `-2`, then `-3` — the generator refuses to overwrite a plan, and so does this skill; old
plans are records, never edited or deleted. The selection file is working material, not a record:
it belongs in a scratch location, never under `profile/`. Everything tunable lives in
`scripts/generate.config.json`, never in the script and never in prose.

## Choosing from the brief

The brief hands over a budget and a legal candidate pool per muscle group. Everything inside it is
yours: which candidate fills a slot, what order the session runs in, what pairs as a superset, how
many reps inside the band, and how close to failure each exercise sits. `coaching.md` is what to
decide it with — read it before choosing, not after.

- **The pool is a boundary, not a ranking to obey.** Its order is the old fit's arithmetic, kept
  as a starting point. An exercise further down that suits this person better is the right answer.
- **Choose an exercise the brief did not offer and the run is refused**, by name — the pool
  already had the equipment, benchmarks and exclusions applied. Widen it by changing the rules and
  re-running the brief.
- **Say what you decided and why**, in one or two lines, before the echo step. A plan whose
  reasoning is invisible cannot be argued with; making these decisions arguable is the point.
- Only two training rules are checked — `coaching.md` § What the script actually enforces. Every
  other rule there is yours to honour, and yours to name when you knowingly go against one.

## No Python

If `scripts/generate.py` cannot run here, do not imitate it by hand. Choosing exercises is your
job; working out which ones are legal and how many sets each muscle is owed is not. Write nothing,
say so, and hand back the commands above.
A missing plan is recoverable; a plausible-looking wrong one is not.

## Before writing

Show, before any file lands:

- The **planned-versus-allocated table** — per muscle group, allocated versus what the chosen
  week delivers.
- The **week itself** — each day's exercises, sets and reps.
- **Every warning**, in plain English: a short group ("cannot reach the hamstrings allocation —
  6 of 9 sets"), an exclusion that matched nothing, an unplaceable must-include.
- The **exact paths** about to be written.

Also say, in a line or two, **why the week looks the way it does** — the choices that were yours
rather than the arithmetic's.

Let the person veto or adjust. An exercise swap is a changed selection and another compose: the
choice was yours to make, so remaking it is cheap, and a preference they want to last still
belongs in their `rules.md`. Either route recomputes the volume arithmetic, which is why you
never hand-edit an exercise into the generator's output. If they abandon here, write nothing.

## What this skill never does

- Never writes to `profile.json`, `programs/`, `rules.md`, or `assets/datasets.json`. Its
  entire writable surface is `profile/plans/`.
- Never re-interviews. Profile changes go through onboarding.
- Never computes or adjusts volume targets — that is `volume.py`'s job alone.
- Never commits the dataset cache or anything under `profile/`.
- Never hides a shortfall. If the targets cannot be met, the plan says so in `warnings` and the
  person hears it in the echo step.
