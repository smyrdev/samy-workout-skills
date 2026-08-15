# Plan quality rubric

You are scoring one generated training plan for one persona. You receive three things:
this rubric, the persona's narrative (`persona.yaml`), and the plan itself (`plan.md`,
which includes the weekly volume table and any shortfall warnings). Judge only from
these — do not assume facts about the person or the exercise dataset that are not in
front of you.

Score the five criteria below, in this exact order, using these exact names. For each
criterion, state your evidence (citing specific exercises, days, or lines of the plan)
and your reasoning first, then give an integer score from 1 to 5. The anchors define
the scale; scores between anchors interpolate.

## selection_suitability

Do the chosen exercises fit this person's experience level and equipment, and does each
one earn its slot?

- **5** — every exercise is performable with the persona's equipment as listed;
  complexity matches experience (no advanced barbell lifts for a novice, no machine-only
  picks for someone with a full gym who wants to learn free weights); no two exercises
  duplicate the same muscle through the same movement pattern.
- **3** — the selection works, but one or two slots are wasted on near-duplicates or
  slightly odd fits (e.g. two curl variations in a short session).
- **1** — multiple exercises the persona cannot perform with their equipment or safely
  at their level, or the selection is dominated by redundant picks.

## balance_and_coverage

At the week level, is the plan balanced across movement patterns, and does the day
layout respect the split's intent?

- **5** — pushing, pulling, and hip-hinge work are in sensible proportion across the
  week; no muscle is trained hard on back-to-back days against the split's intent;
  every major muscle the program targets appears somewhere in the week.
- **3** — mostly balanced, with one visible tilt (e.g. pressing volume clearly
  outweighing pulling) or one questionable back-to-back placement.
- **1** — a major pattern or muscle group is missing or starved while another is
  saturated, or consecutive days repeatedly hammer the same muscle.

## ordering_and_structure

Within each session, is the exercise order sensible, and does the session plausibly fit
the time available?

- **5** — compound, technically demanding lifts come before isolation work in every
  session; the flow within a session is coherent (no ping-ponging between muscle groups
  for no reason); the number of exercises and sets plausibly fits the profile's session
  minutes.
- **3** — ordering is mostly right with one or two lapses (an isolation lift ahead of a
  compound, a session that looks slightly overstuffed for the time slot).
- **1** — ordering is careless (heavy compounds routinely last, fatiguing isolation
  first), or sessions clearly cannot fit the stated session length.

## persona_fit

Does the plan honor this specific person — the narrative's goal detail, injuries, and
preferences, and any personal rules — in spirit, not just in letter?

- **5** — every injury, preference, and goal detail in the narrative is visibly
  respected in the plan (nothing aggravates a stated injury, stated preferences shape
  the selection); if the persona has personal rules (exclusions, muscle focus), each one
  is observably honored.
- **3** — the plan is generically reasonable and violates nothing outright, but ignores
  a stated preference or misses an easy chance to serve the persona's specific goal.
- **1** — the plan contradicts the narrative: it programs something a stated injury
  forbids, or plainly disregards a personal rule.

## red_flags

Anything a competent coach would veto outright. List each red flag you find (with the
evidence), or state that there are none — and still give this criterion a score like
the others: 5 when there is nothing to veto, 3 when there is a borderline call you
would question but not veto, 1 when anything veto-worthy is present. Red flags
include, for example: an exercise that directly loads a stated injury; a dangerous or
nonsensical exercise for this person's level; a session so overloaded it is unsafe or
impossible; a plan element that contradicts the program's own stated goal.

**Any red flag caps the overall score at 2, no matter how well the other criteria
score.** You compute the overall yourself and apply this cap.

## Out of scope

Do not score any of the following — they are checked deterministically elsewhere, and
you lack the information to verify them:

- schema validity of any file;
- volume arithmetic — whether weekly set counts hit the computed targets (the plan's
  volume table and shortfall warnings are input for the criteria above, not something
  to re-audit);
- whether an exercise actually exists in the source dataset.

If a plan seems to fail in one of these ways, note it in your summary but do not let it
move a criterion score.
