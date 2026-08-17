# Generation tuning — brainstorm findings (paused 2026-08-17)

Status: brainstorm paused mid-design at the goal-steering question. This file captures the
root-cause analysis and the decisions already made so the session can resume without
re-deriving anything. Companion prompt: `2026-08-15-generation-tuning-brainstorm-prompt.md`.
Open items live in `todo.md`.

Baseline: eval run `evals/results/2026-08-15-1941/` — every persona ≤ 2/5, all red-flag
capped. The six findings below were confirmed against `generate.py`, `generate.config.json`,
`datasets.json`, the dataset schema, and the shiva plan.

## Root causes, mapped to the six eval findings

1. **Obscure entries beat staples.** The only canonicality signal in `marginal_score()` is
   `name_length_penalty` (0.02/char), and it is *backwards* at the variant level: "squat jerk"
   (10 chars) beats "barbell squat" (13) by 0.06 with a byte-identical volume map; "push-up"
   (−0.14) crushes "barbell bench press" (−0.38). The docs' assumption "short names are the
   canonical movements" fails exactly where it matters.

2. **primary_goal doesn't steer selection.** It touches one thing only: `reps_by_goal`
   (rep ranges). Selection is completely goal-blind — a "strength" persona gets no
   squat/bench/deadlift because nothing asks for them.

3. **Bands/bodyweight fill slots in full gyms.** `equipment_tiers` encode *availability*,
   not desirability. Band and bodyweight sit in tier 1 alongside barbell, so "tier ≤ N"
   can never prefer the barbell. There is no desirability signal at all.

4. **No complexity gate.** Nothing reads `experience.lifting` (canonical enum:
   `none/beginner/intermediate/advanced`). Bonus find: "squat jerk" is
   `category: "strength"` in the dataset with the "Barbell squats" volume profile — by the
   dataset's own schema prose, jerks belong in `olympic` (which `category_filter` excludes).
   That is an upstream data bug, separate from (but hidden by the absence of) a gate here.

5. **Planned sets overshoot allocation** (shiva: shoulders 36 planned vs 20 allocated,
   core 30 vs 8). `marginal_score()` rewards sets landing in needy groups but never *charges*
   for flooding already-full ones, and co-prime-mover 1.0 coefficients ride along
   undiscounted (`indirect_discount` only touches 0.5s) — every press variant carries
   Front Delts 1.0 into shoulders. `repair_shortfalls()` then adds more sets on carriers
   without weighing their passenger volume.

6. **Near-duplicates across the week.** `max_per_volume_profile_per_session` is per
   *session* only, and `repeat_penalty` keys on exercise *id* — so pull-up, chin-up, and
   biceps pull-up are each a "fresh" pick and three vertical-pull variants eat three
   weekly slots.

## Structural constraint that shapes any fix

Config may only speak *canonical* vocabulary (today: the 10 muscle groups, the experience
enum, goal names). `volume_profile`, `movement_group`, and equipment strings are dataset
vocabulary. So every new steering signal follows the `muscle_map` pattern: **the descriptor
maps dataset vocabulary onto a canonical vocabulary; config attaches numbers to the
canonical names.** Examples: equipment strings → equipment classes (free_weight / machine /
band / bodyweight …); volume_profiles → movement patterns (squat / hinge /
horizontal_press / vertical_pull …); staple markings on rows → one staple bonus number.

## Decisions made in the session

- **Dataset and this repo are independent projects** — `docs/generation.md` already commits
  to that ("dataset repository stays pure data + schema"; "a new dataset is a new entry,
  not a fork"). Therefore the staple/canonicality signal lives in the **descriptor**
  (this consumer's opinion), not in an upstream field. If a future dataset ships a
  popularity/difficulty field, the descriptor points at it — same mechanism, different
  source. Curation surface is small: ~36 volume_profiles, 1–3 preferred names each.
- **Upstream data bugs get fixed upstream, non-blocking** — e.g. recategorizing squat jerk
  as `olympic` in smyrdev/exercises-dataset is a dataset-project task; this repo's fixes
  must not wait on it (and must handle advanced movements regardless, because any dataset
  will contain some).
- **Experience gate is a hard gate, pattern-based** — a descriptor `experience_gates`
  section mirroring the existing `benchmark_gates` shape: name patterns each tagged with a
  minimum `experience.lifting` level; `generate.py` filters rows below it. ~15 lines covers
  the flagged offenders (jerk, snatch, clap, plyo, pistol, muscle-up, glute-ham, drop
  push…). Per-exercise level annotation was considered and deferred: that is upstream
  dataset enrichment, i.e. the separate project. Rationale for hard over soft: judges treat
  a single advanced movement on a novice as a red-flag veto, so a score penalty that
  merely makes leaks rare still caps the score.
- **PR sequencing**: (1) merge the evals harness PR (this branch) first — it is the
  measurement instrument; (2) generation-tuning PR, verified by rerunning
  `bash evals/run-evals.sh` (cheap iteration via `--skip-judge` plan diffs);
  (3) agentskills.io layout restructure (SKILL.md / scripts/ / references/ / assets/) as
  its own mechanical PR, last, so tuning never rebases over renames.

## Where the brainstorm stopped

At goal steering (finding 2): should `primary_goal` steer via score bias only, via
guaranteed weekly anchor patterns (strength ⇒ squat/hinge/horizontal_press at least once,
placed like must_include), or both? Samy wants **science research** before deciding —
what does the evidence actually say a strength vs hypertrophy vs both block must contain?
Unresolved alongside it: whether findings 1–3+5 collapse into one scoring function with
config-driven terms (staple bonus, goal-pattern bonus, equipment-class preference,
overshoot penalty) replacing `name_length_penalty`, with 4 (gate) and 6 (weekly
profile cap / repeat-penalty rekeying) as the two non-scoring mechanisms. That shape looked
promising but was not agreed.
