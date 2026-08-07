# Generation — rationale

The machine-readable contracts are
[`skills/generation/schema/plan.schema.json`](../skills/generation/schema/plan.schema.json) and
[`skills/generation/schema/rules.schema.json`](../skills/generation/schema/rules.schema.json),
with [`skills/generation/examples/`](../skills/generation/examples/) holding a filled-in sample of
each — the plan example is genuine generator output, not hand-written. When this document and a
schema disagree, the schema wins and this document is the bug. For "what do I literally type in
`rules.json`", see [`skills/generation/FIELDS.md`](../skills/generation/FIELDS.md) — this file is
the *why*.

---

## The division of labor

Three parties, one number each:

| Who | Owns | Never touches |
|---|---|---|
| `volume.py` (onboarding) | how many weekly sets each muscle group gets | exercise selection |
| `generate.py` (generation) | which exercises deliver those sets | the set targets |
| the person (`rules.json`) | exclusions, focus, ordering | — it's their training |

The volume block inside `programs/program-*.json` is the interface between the first two. That is
why generation refuses a program file without one instead of estimating targets itself: the
moment two scripts can produce "weekly sets per muscle", they can disagree, and a plan that
quietly used the wrong targets looks exactly like a correct plan.

## The dataset descriptor

`skills/generation/datasets.json` holds **everything** the generator knows about any particular
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
arithmetic the fit works against.

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

## The fit

`generate.py` fills sessions round-robin — slot 1 on every day, then slot 2 — so the week comes
out balanced instead of front-loading day 1 and leaving day 6 empty. Each pick maximizes the
marginal useful volume (coefficients capped by what each group still needs), with a penalty for
exercises already used this week (variety), a bonus for focused groups, and a mild penalty per
character of name — in this dataset the canonical movements have the short names, and without
that steer the widest-map oddball variations win every tie. A repair pass then adds sets to
prime movers of any still-short group. Whatever remains short is reported in `warnings` — never
silently absorbed.

Three deliberate calibrations, all tunable in `generate.config.json`:

- **Indirect volume counts at a discount toward the fit** (`indirect_discount`, default half —
  so a 0.5 synergist coefficient counts 0.25). At face value, the 0.5s from heavy compounds
  "cover" arms, shoulders and core before a single direct exercise for them is picked; the
  discount forces every group to earn real direct work. The plan JSON embeds each exercise's raw
  volume map, so any other accounting can be recomputed from the record.
- **One exercise per movement pattern per session** (`max_per_volume_profile_per_session`,
  using the dataset's fine-grained `volume_profile`) — otherwise two near-identical dip
  variants can land in the same day. The coarser `movement_group` cap still applies on top.
- **Sessions may come in under the exercises-per-session cap.** The cap is a ceiling derived
  from the session-length answer, not a quota: compounds deliver several groups per set, so the
  allocation is often met with fewer exercises than the ceiling allows. Stuffing the session
  past the allocation would overshoot the volume model's targets — the person can always ask
  for more via focus rules or a bigger allocation.

The fit is **deterministic**: stable sorts, explicit tie-breaks (name, then id), no randomness,
no clock except the `--today` override. The same profile, program, rules, dataset and date
produce a byte-identical plan. Boring on purpose: a surprising plan should always be explainable
by an input that changed.

Session ordering is a user-visible rule list (`order` in `rules.json`), applied top-down as
successive sort keys. The default puts pinned exercises first, trailer groups (core, calves)
last, and compounds before isolation in between.

## Plans are append-only records

A plan file is never overwritten — the generator refuses, and same-day re-runs suffix `-2`,
`-3`, exactly like program files. The `.md` render next to the `.json` is the person's copy:
annotate it, cross things out, print it. The `.json` is the structured record and embeds the
dataset commit hash, the merged rules, and every exercise's volume map, so it stays readable and
auditable after the dataset cache is deleted or the upstream moves on.

## What is deliberately not here (v1)

- **No weights, no progression.** The plan says movements, sets and rep ranges. Load selection
  and week-to-week progression are the session-logging feature's job, when it exists.
- **No per-exercise scheduling intelligence** (supersets, rest times, exercise pairing).
- **No cardio or mobility programming.** The dataset's cardio and stretch categories are
  filtered out by the descriptor; widening `category_filter` is the extension point when a
  volume model for them exists.
- **No item-level equipment.** Tiers remain the equipment model, as in onboarding.
