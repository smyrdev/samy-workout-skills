# Generation rules

What the flow points at that is not the flow itself: what the inputs must look like, how the
dataset cache works, what to say before writing, what this skill never does.

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
- An older `profile/rules.json` is still read, so nothing breaks — but the Markdown file is what
  the person is pointed at, and what a snippet is written for.
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

```
python skills/generation/scripts/generate.py \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --write profile/plans/plan-<today>.json \
  --write-md profile/plans/plan-<today>.md
```

Add `--rules profile/rules.md` when it exists. If today's filename is taken,
suffix `-2`, then `-3` — the generator refuses to overwrite a plan, and so does this skill; old
plans are records, never edited or deleted. Everything tunable lives in
`scripts/generate.config.json`, never in the script and never in prose.

## No Python

If `scripts/generate.py` cannot run here, do not imitate it by hand. Write nothing, say so, and
hand back the command above. A missing plan is recoverable; a plausible-looking wrong one is not.

## Before writing

Show, before any file lands:

- The **planned-versus-allocated table** — per muscle group, allocated versus what the fitted
  week delivers.
- The **week itself** — each day's exercises, sets and reps.
- **Every warning**, in plain English: a short group ("cannot reach the hamstrings allocation —
  6 of 9 sets"), an exclusion that matched nothing, an unplaceable must-include.
- The **exact paths** about to be written.

Let the person veto or adjust. A swap is a rules change and a re-run — a `--rules` file for one
cycle, or their `rules.md` for always — so the volume arithmetic stays true; never
hand-edit an exercise into the generator's output. If they abandon here, write nothing.

## What this skill never does

- Never writes to `profile.json`, `programs/`, `rules.md`, or `assets/datasets.json`. Its
  entire writable surface is `profile/plans/`.
- Never re-interviews. Profile changes go through onboarding.
- Never computes or adjusts volume targets — that is `volume.py`'s job alone.
- Never commits the dataset cache or anything under `profile/`.
- Never hides a shortfall. If the targets cannot be met, the plan says so in `warnings` and the
  person hears it in the echo step.
