# Field guide

What to literally type in the generation skill's user-facing files. The schemas in
`skills/generation/assets/schema/` are the enforced contract; this is the short version. Validate with
`python scripts/validate-skills.py` from the repository root.

## `profile/rules.md` — yours to write

Standing preferences, read on every run and written by nobody but you. It is plain Markdown, so
there is no punctuation to get wrong: copy
`skills/generation/assets/examples/rules.example.md` to `profile/rules.md` and edit the bullets.

Three rules cover the whole format:

- `## Heading` starts a section. The headings below are the only ones allowed — a misspelled one
  stops the run rather than being quietly ignored.
- `- item` is one value. One per line.
- Everything else is a note to yourself and is ignored, so explain your own choices in place.

Delete a section entirely and the default from `skills/generation/scripts/generate.config.json`
applies. Keep the heading with no bullets under it to mean "none of these" — that is how you
switch a default off.

```markdown
## Exclude exercises
- burpee

## Focus muscles
- shoulders
```

| Section | Put in | Note |
|---|---|---|
| `## Exclude exercises` | exact dataset exercise names, one per bullet | case-insensitive, spelling exact; an unknown name becomes an `unknown_exclude_exercise:<name>` warning, never a silent no-op |
| `## Exclude equipment` | dataset equipment values, e.g. `smith machine` | avoided even if your gym tier allows them; same warning on unknowns |
| `## Exclude movement groups` | dataset movement families, e.g. `Shrugs` | |
| `## Exclude muscles` | one or more of `chest`, `back`, `shoulders`, `biceps`, `triceps`, `quads`, `hamstrings`, `glutes`, `calves`, `core` | the group's target is dropped, not rerouted |
| `## Focus muscles` | same ten values | picked earlier and more often when candidates tie; allocations unchanged |
| `## Must include` | exact dataset exercise names | guaranteed a slot when tier, benchmark gates and exclusions allow; otherwise an `unmatched_must_include:<name>` warning |
| `## Order` | rules, primary sort first, later rules break ties | omit the section for the config default |

A `profile/rules.json` from before this file was Markdown is still read, so an old one keeps
working — but `rules.md` is the format to write now, and the one the skill offers snippets for.
`skills/generation/assets/schema/rules.schema.json` describes what the generator parses your
Markdown into; you never type JSON.

Order rules: `must_include_first` (pinned exercises lead) · `trailer_groups_last` (config
`trailer_groups`, core and calves by default, close the session) · `compound_before_isolation` ·
`focus_muscles_first` · `large_groups_before_small` (bigger weekly allocations earlier).

## `profile/plans/plan-YYYY-MM-DD.md` — also yours

The human-readable render. Annotate, cross out, print — it is a snapshot for you, not an input.

## `profile/plans/plan-YYYY-MM-DD.json` — generated, not hand-written

The structured record: who, program echo, dataset name and commit, merged rules, allocated versus
planned sets per group, every session, every warning. Want a different plan? Change `rules.md`
(or the program answers via onboarding) and generate again — a new dated file appears, the old one
stays. Hand-editing this file makes its volume arithmetic quietly wrong.
