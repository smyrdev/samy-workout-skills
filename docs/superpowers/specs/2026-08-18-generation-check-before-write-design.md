# Generation: check before write

**Problem.** The generation flow documents two generator commands — `--brief`, then
`--selection … --write … --write-md`. Nothing between choosing and writing shows the agent the
generator's own planned-versus-allocated table, so it either sums sets by hand (and gets the
synergist discount wrong) or writes first and echoes after. Eval run 2026-08-17, generation
case 1: plan written before the table was shown, hand tally disagreed with the generator, a
second `-2` pair was written.

**Fix (soft — guidance, no new refusal).** The generator already composes without writing when
`--write` is absent. Make that the documented, visible middle step.

## Changes

1. `skills/generation/references/rules.md` § Running the generator — three commands:
   `--brief`; `--selection` without `--write` (the **check**: its `targets` table and `warnings`
   are what the echo step shows); the same command again with `--write` and `--write-md`.
   One sentence: the planned column is the generator's number, never a hand tally.
2. `skills/generation/SKILL.md` — step 6 says the choices go back *without* `--write` first and
   that output is the echo; new gotcha under the same rule ("check first, write second — a
   hand-tallied table has produced a second plan file").
3. `skills/generation/scripts/generate.py` — every `--selection` run prints a compact
   `muscle  allocated  planned` table plus the warnings to **stderr**, before the stdout JSON or
   the `wrote …` lines. stdout is unchanged so existing consumers and tests keep working.
   No new flags. `--write` still refuses exactly what it refuses today.
4. `tests/skills/test-generation-script.sh` — one case: `--selection` without `--write` writes
   nothing under the plans dir and its stderr contains the table header and every muscle group.
5. `docs/generation.md` — wherever the two-command flow is described, name the check step.

## Out of scope

Restructuring `generate.py`, a `--check` flag, a `confirmed` gate in the selection file, eval
assertion changes (generation case 1's assertions stay as written; this fix is meant to make
them pass).
