# Brief: effective volume per candidate

**Problem.** Each brief candidate carries `volume`, the dataset's raw per-muscle coefficients
(`{"chest": 1.0, "core": 0.5}`). The generator counts anything under 1.0 at `indirect_discount`
(default 0.5), so `core: 0.5` really contributes 0.25 per set. The brief never says so; every hand
estimate in the eval runs was off by exactly this, and the agent had to read `generate.py` to find
out. `plan.schema.json`'s `targets` description repeats the same wrong arithmetic ("0.5 for
indirect ones").

**Fix (option A).** Add `effective_volume` beside `volume` in each brief candidate. `volume` stays
(the plan record embeds the raw map). One self-test invariant, one CLI test, two doc lines.

## Changes

1. `skills/generation/scripts/generate.py` — `rank_candidates` emits
   `"effective_volume": r["effective"]` after `"volume": r["muscles"]`. `prepare()` already
   computes `row["effective"]` (the discount applied); no arithmetic is added.
2. `run_self_test` — one invariant on the fixture brief: for every candidate and every muscle,
   `effective_volume[g] == volume[g]` when `volume[g] >= 1.0`, else
   `== volume[g] * config["indirect_discount"]`, and the key sets are equal.
3. `tests/skills/test-generation-script.sh` — the brief carries `"effective_volume"`, and a python
   one-liner over `brief-a.json` asserts the same equality with the config's discount (no literal
   0.5 in the test — the number lives in the config).
4. `docs/generation.md` § "The brief and the selection", the "Indirect volume counts at a
   discount" bullet — add: "The brief shows both: `volume` is the raw map the plan records,
   `effective_volume` is what the generator will actually count — sum that column, not the raw one."
5. `skills/generation/references/coaching.md` § What the script actually enforces — in the sentence
   "what each candidate is worth" add the parenthetical "(`effective_volume` in the brief — the
   only column whose sum matches the check table)".
6. `skills/generation/assets/schema/plan.schema.json` `targets.description` — replace "(each set
   adds 1.0 for direct muscles, 0.5 for indirect ones)" with "(each set adds the exercise's
   coefficient for direct muscles, and the coefficient times the config's indirect discount for
   indirect ones)".

## Out of scope

`rules.md`, either `SKILL.md`, the plan JSON shape, any change to how volume is counted.
