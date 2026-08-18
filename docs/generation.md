# Generation — rationale

The machine-readable contracts are
[`skills/generation/assets/schema/plan.schema.json`](../skills/generation/assets/schema/plan.schema.json),
[`skills/generation/assets/schema/selection.schema.json`](../skills/generation/assets/schema/selection.schema.json)
and [`skills/generation/assets/schema/rules.schema.json`](../skills/generation/assets/schema/rules.schema.json),
with [`skills/generation/assets/examples/`](../skills/generation/assets/examples/) holding a filled-in sample of
each — the plan example is genuine generator output, composed from the selection example next to
it. The training-design knowledge the coach applies between the two lives in
[`skills/generation/references/coaching.md`](../skills/generation/references/coaching.md). When this document and a
schema disagree, the schema wins and this document is the bug. For "what do I literally type in
`rules.md`", see [`generation-fields.md`](generation-fields.md) — this file is
the *why*.

`rules.schema.json` is the odd one out: the person writes `profile/rules.md` as Markdown, and the
schema describes what `generate.py` parses that into. Markdown is what a human edits between
training blocks with no punctuation to get wrong; the schema still pins the vocabulary, so
`default_rules` in `generate.config.json` and a parsed `rules.md` are checked against one contract.

---

## The division of labor

Three parties, one number each:

| Who | Owns | Never touches |
|---|---|---|
| `volume.py` (onboarding) | how many weekly sets each muscle group gets | exercise selection |
| `generate.py` (generation) | which exercises are *legal*, and what the week owes each muscle | which of them to use |
| the coach (`coaching.md`) | which exercise, in what order, paired how, at what effort | the set targets and the pool |
| the person (`rules.md`) | exclusions, focus, ordering | — it's their training |

The volume block inside `programs/program-*.json` is the interface between the first two. That is
why generation refuses a program file without one instead of estimating targets itself: the
moment two scripts can produce "weekly sets per muscle", they can disagree, and a plan that
quietly used the wrong targets looks exactly like a correct plan.

## The dataset descriptor

`skills/generation/assets/datasets.json` holds **everything** the generator knows about any particular
dataset: repository and ref, file paths, field names, category filter, equipment→tier tables,
muscle vocabulary mapping, benchmark gates. `generate.py` is deliberately dataset-agnostic — it
reads shapes through the descriptor and refuses anything unmapped.

Why a descriptor instead of code, or of a query script shipped inside the dataset repository:

- **The dataset repository stays pure data + schema.** A query script there would be one
  language, one consumer's needs — and the next dataset wouldn't have one, so the generator
  would need a fallback path anyway.
- **A new dataset is a new entry, not a fork.** Different field names, a different muscle
  vocabulary, different equipment strings — all absorbed by the mapping tables.
- **Refusal beats guessing.** When the upstream dataset adds a muscle or an equipment type the
  descriptor doesn't know, the run fails with the exact list of unmapped names and where to add
  them. Silent best-effort mapping would misroute volume, which is invisible in the output.

The default entry describes
[smyrdev/exercises-dataset](https://github.com/smyrdev/exercises-dataset): ~1,300 exercises, of
which ~1,100 carry a `volume` map — per-muscle involvement following the fractional-set
convention (1.0 = prime mover, 0.5 = meaningful synergist, after Schoenfeld et al. 2019). Each
performed set of an exercise adds its coefficients to the week's per-muscle totals; that is the
arithmetic the volume targets are counted in.

### Muscle mapping

The dataset speaks a 22-muscle vocabulary; the volume model speaks 10 groups. `muscle_map`
collapses the former onto the latter (delts → shoulders, lats/upper back/traps → back,
abs/obliques/lower back → core, …). When two dataset muscles land on the same group, the
exercise's coefficient for that group is the **max**, not the sum — a row that hits three parts
of the back is still one back exercise per set, not three.

`muscle_ignore` names vocabulary that is deliberately dropped (neck, in the default entry: the
volume model has no neck group and inventing one is a schema change, not a mapping decision).
Ignored-only exercises simply never appear.

### Equipment tiers

The profile's gym type became `equipment_tier` (1–4) in the volume block. The descriptor buckets
every dataset equipment string into a tier; a person at tier N draws from tiers ≤ N. Free
weights, bands and small home equipment are tier 1; the machine families tier 2; specialty
cardio/strongman machines tier 3; tier 4 is currently empty (an everything-gym allows all of the
above). The mapping is a judgment call — that is exactly why it lives in the editable descriptor
and not in code.

### Benchmark gates

The profile's self-reported strength benchmarks gate exercise families: no unassisted pull-up
variants for someone who can't yet do five, no dips for someone who can't do ten — with
`unless_equipment` carving out the assisted versions. The gates are name-pattern based because
that's what the dataset offers; patterns live in the descriptor so a new dataset (or a false
positive) is a data fix.

## The brief and the selection

`generate.py --brief` answers three questions and stops: what may this person legally be given,
how much does each muscle need this week, and how much fits in a session. It hands over a ranked
candidate pool per muscle group and a budget. It does not pick anything.

The pool is what survives filtering: the dataset's category filter, the equipment tier from the
volume block, the benchmark gates, and the person's own exclusions. The ranking is a
marginal-volume score against the full week's targets — a sensible reading order, not a
verdict. `candidates_per_muscle` bounds how many are offered, because a pool nobody can read is
the same as no pool.

The budget has two halves. Each muscle's weekly allocation is spread as evenly as it divides
across the days that train it (17 sets over 3 sessions comes out 6/6/5), and the session's
exercise ceiling is the tighter of two numbers: the one the volume model already derived from the
session-length answer, and the one that falls out of session length divided by the time a set
actually takes — `set_seconds` plus the rest interval for the goal. Longer rests buy fewer
exercises, not a longer workout. Both remain ceilings, never quotas.

Then `--selection` takes the choices back and recomputes everything: what the week delivers per
muscle against what was allocated, with any shortfall reported in `warnings` — never silently
absorbed. Run without `--write`, this is the **check**: the plan JSON goes to stdout and the
allocated-versus-planned table with the warnings goes to stderr, so the coach shows the
generator's numbers before anything is written. The same command with `--write`/`--write-md`
is the write; nothing about the arithmetic changes between the two.

Deliberate calibrations, all tunable in `generate.config.json`:

- **Indirect volume counts at a discount** (`indirect_discount`, default half — so a 0.5
  synergist coefficient counts 0.25). At face value, the 0.5s from heavy compounds "cover" arms,
  shoulders and core before a single direct exercise for them is chosen; the discount forces
  every group to earn real direct work. The brief shows both: `volume` is the raw map the plan
  records, `effective_volume` is what the generator will actually count — sum that column, not
  the raw one. The plan JSON embeds each exercise's raw volume map, so any other accounting can
  be recomputed from the record.
- **The exercise ceiling is a ceiling.** Compounds deliver several groups per set, so an
  allocation is often met with fewer exercises than the ceiling allows. Filling a session to the
  ceiling for its own sake overshoots the volume model's targets.
- **Only two training rules are refused** — an exercise outside the offered pool, and a rep
  target under `rep_floors` on the goals `rep_floor_goals` names. Everything else in `coaching.md`
  is guidance: a number the script can compute is a number the coach should see, not a gate.

**The brief is deterministic; the plan is not.** Stable sorts, explicit tie-breaks (name, then
id), no randomness, no clock except `--today` — the same inputs always produce a byte-identical
*brief*. What gets chosen from it is a coach's judgment, so a plan is no longer reproducible from
its inputs alone. What replaces reproducibility is **auditability**: the brief can be regenerated
and says exactly what was on offer and what each muscle was owed; composing a selection recomputes
every number from scratch; and a surprising plan is explainable either by an input that changed
or by a choice someone made and can be asked about.

Session ordering (`## Order` in `rules.md`, see `docs/generation-fields.md`) is no longer a sort
the script performs: the list travels in the brief as the person's standing instruction and the
coach applies it. Naming a rule that does not exist is still refused.

## Plans are append-only records

A plan file is never overwritten — the generator refuses, and same-day re-runs suffix `-2`,
`-3`, exactly like program files. The `.md` render next to the `.json` is the person's copy:
annotate it, cross things out, print it. The `.json` is the structured record and embeds the
dataset commit hash, the merged rules, and every exercise's volume map, so it stays readable and
auditable after the dataset cache is deleted or the upstream moves on.

## What is deliberately not here

- **No weights, no progression.** The plan says movements, sets, reps and effort. Load selection
  and week-to-week progression are the session-logging feature's job, when it exists. That
  absence is also why asymmetry correction, work capacity and the fatigue index sit in
  `coaching-deferred.md` rather than `coaching.md`: every one of them needs per-set history.
- **No multi-week block.** A plan is one week plus a deload multiplier. RIR is prescribed per
  exercise and does not ramp across a mesocycle.
- **No cardio or mobility programming.** The dataset's cardio and stretch categories are
  filtered out by the descriptor; widening `category_filter` is the extension point when a
  volume model for them exists.
- **No item-level equipment.** Tiers remain the equipment model, as in onboarding.
