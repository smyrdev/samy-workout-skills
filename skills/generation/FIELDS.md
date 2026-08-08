# Field guide

For hand-editing the generation skill's user-facing files. The schemas
(`schema/rules.schema.json`, `schema/plan.schema.json`) are the enforced contract; this is the
plain-English version. Validate with `python scripts/validate-skills.py` from the repository root
when you are done.

## `profiles/<slug>/rules.json` — yours to write

Your standing preferences, read on every generation run and written by nobody but you. Start from
`examples/rules.example.json`. Every section is optional — leave one out and the defaults in
`scripts/generate.config.json` apply.

The five section names below (`$schema_version`, `exclude`, `focus`, `order`, `notes`) are the
only ones accepted. A misspelled section — `excludes` for `exclude` — is refused with an error
rather than warned about, because ignoring it would silently disable every rule you wrote inside
it.

### `$schema_version`
Always the quoted string `"1.0"`. Do not change it by hand.

### `exclude.exercises`
Exact exercise names from the dataset, e.g. `["burpee", "barbell squat"]`. Case does not matter,
spelling does — a name the dataset does not contain shows up as an
`unknown_exclude_exercise:<name>` warning in the plan instead of silently doing nothing.

### `exclude.equipment`
Dataset equipment values you want avoided even though your gym tier allows them — e.g.
`["smith machine"]`. Same warning behavior for unknown values.

### `exclude.movement_groups`
Whole dataset movement families to skip, e.g. `["Shrugs"]`.

### `exclude.muscles`
Muscle groups to drop from the plan entirely (injury, personal choice). One or more of:
`chest`, `back`, `shoulders`, `biceps`, `triceps`, `quads`, `hamstrings`, `glutes`, `calves`,
`core`. The group's target is removed — the plan will not quietly reroute those sets elsewhere.

### `focus.muscles`
Groups this program should bias toward, from the same ten values. Focused groups get picked
earlier and more often when candidates are otherwise equal; they do not change the allocated set
counts, which belong to the volume model. A value that is not one of the ten — or one you also
excluded — comes back as an `unknown_focus_muscle:<name>` warning.

### `focus.must_include`
Exact dataset exercise names guaranteed a slot, e.g. `["barbell bench press"]` — honored as long
as your equipment tier, benchmark gates, and exclusions allow the exercise; otherwise the plan
carries an `unmatched_must_include:<name>` warning.

### `order`
How each session is sorted, as a list applied top-down — the first rule is the primary sort key,
each later rule breaks the remaining ties. The valid rules are whatever `order_rules` in
`scripts/generate.config.json` lists; today that is:

- `must_include_first` — your pinned exercises lead the session
- `trailer_groups_last` — trailer groups (see `trailer_groups` in the config; core and calves by
  default) close the session
- `compound_before_isolation` — exercises hitting more muscle groups come earlier
- `focus_muscles_first` — your focused groups come earlier
- `large_groups_before_small` — groups with bigger weekly allocations come earlier

An unrecognized rule stops the run rather than being skipped. Omit `order` entirely to use the
default in `scripts/generate.config.json`.

### `notes`
Freeform coaching guidance, one string per note — e.g.
`["prefer supersets when short on time", "keep the first exercise heavy"]`. The fitting algorithm
ignores these entirely; the review step that runs after it reads them and revises the plan
accordingly. Write them the way you would brief a coach. Unlike every other section there is no
vocabulary to match, so nothing here ever produces a warning.

## `profiles/<slug>/plans/plan-YYYY-MM-DD.md` — also yours

The human-readable render of a generated plan. Edit it freely — annotate weights, cross out a
day, print it. It is a snapshot for you, not an input to anything.

## `profiles/<slug>/plans/plan-YYYY-MM-DD.json` — generated, not hand-written

The structured record of the same plan: program echo, dataset name and commit, the merged rules it
used, per-group volume, every session, every warning. Two optional fields record the coach review
that runs after the fitter: a root `revisions` array — one plain-English line per change, absent
when the plan is untouched fitter output — and, per session, a `supersets` array of exercise-id
pairs to perform alternated rather than back to back. Each group under `targets` carries
`allocated` (what the volume model budgeted), `direct` and `planned` (direct-only and total sets
the week delivers), and `balance` — the group's share of the week's direct sets divided by its
share of the allocation. **Compare on `balance`, not on `direct` minus `allocated`.** The volume
model budgets sets as though one set trained one muscle, while a real set trains close to two, so
`direct` sits above `allocated` for every group and the gap on its own means nothing. If you want a
different plan, change your `rules.json` (or re-run with different program answers) and generate
again — a new dated file appears and the old one stays as a record. Hand-editing this file makes
its volume arithmetic quietly wrong, which is worse than any problem it solves.
