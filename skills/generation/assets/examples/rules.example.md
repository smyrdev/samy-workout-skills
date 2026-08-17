# My generation rules

Copy this to `profile/rules.md` and edit it. Every section is optional — delete one
entirely and the default from `skills/generation/scripts/generate.config.json` applies.
Leave a section's heading with no bullets under it to mean "none of these".

Anything that is not a `## Section` heading or a `- item` bullet is a note to yourself
and is ignored, so write as much or as little around them as you like.

## Exclude exercises

Exact dataset names, case-insensitive. A name the dataset does not have comes back as a
warning on the plan, never a silent no-op.

- burpee

## Exclude equipment

Avoided even when your gym tier allows them.

## Exclude movement groups

## Exclude muscles

One or more of: chest, back, shoulders, biceps, triceps, quads, hamstrings, glutes,
calves, core. The group's target is dropped, not spread over the others.

## Focus muscles

- shoulders

## Must include

Guaranteed a slot when tier, benchmark gates and exclusions allow.

- barbell bench press

## Order

Session ordering, primary sort first, each later rule breaking remaining ties.

- must_include_first
- trailer_groups_last
- compound_before_isolation
- focus_muscles_first
- large_groups_before_small
