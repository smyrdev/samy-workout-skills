# Working in this repository

## The skill is portable — keep it that way

`skills/onboarding/SKILL.md` is the source of truth and must stay runnable by **any** LLM agent, not
just Claude Code. In that file:

- No vendor tool names. Write "ask the person, offering these options" — not "call
  `AskUserQuestion`". Write "save the file" — not "use the Write tool".
- No absolute or Windows-specific paths. Everything is relative to the repository root.
- Frontmatter carries `name` and `description` only. Vendor-specific keys belong in the wrapper.

`.claude/skills/onboard/SKILL.md` is a **pointer, not a fork**. It carries the Claude Code
frontmatter and the environment bindings, and nothing else. The moment someone copies the flow steps
into it, the two versions start drifting and the bug is invisible. If a change is needed in the
flow, it goes in the portable file.

## Profiles

- `profiles/<slug>/profile.json` is written by the onboarding skill and by nothing else.
- `profiles/` is gitignored in full except `.gitkeep`. Never commit a real profile, never suggest
  force-adding one.
- `skills/onboarding/profile.example.json` is the schema of record. Any field change updates the
  example, `docs/schema.md`, and the interview in the same commit, and a breaking change bumps
  `$schema_version`.
- Never merge two people into one profile. A slug collision with a different name gets suffixed and
  announced.

## Design rules that look like mistakes

These are deliberate. Do not "fix" them without a reason that survives the explanation below.

- **The profile stores per-cycle answers** — goal, days per week, session length, split, deload.
  They are defaults the generation skill re-confirms, not commitments. Do not clean up the schema by
  moving them out; the whole point is that a returning person clicks "same as last time".
- **Age is never stored, only `date_of_birth`.** A stored age is wrong the year after it is written.
- **Bodyfat is a bracket string and `session_minutes` is a range string.** Storing a number would
  assert a precision the person never gave. The midpoint and exercise-cap mappings live in
  `docs/schema.md` and are the consumer's job.
- **Measurements keep the user's own unit** rather than normalising to metric on disk. Round-tripping
  a conversion on every update introduces float drift.
- **`derived` is all nulls on disk.** It is documentation naming the four computed values so two
  skills cannot disagree about how to compute them — not a cache to populate.
- **v1 models equipment as gym type only.** No item-level checklist without a `$schema_version` bump.

## Docs

- `docs/onboarding.md` is the original hand-written spec, typos and all. **Leave it untouched** — it
  is byte-identical to a copy in the sibling `samy-workouts` repository, and diverging them creates
  a "which one is canonical" problem for no runtime gain. Its empty `## Overwire and toturial`
  heading is a note about a missing overview, satisfied by `README.md`.
- `docs/schema.md` is the clean, canonical field reference. Changes go there.

## Not in scope yet

Workout generation is specified at the end of `skills/onboarding/SKILL.md` but not built. When it
lands: it resolves profiles the same way, never writes to `profile.json`, and puts its output under
`profiles/<slug>/plans/`.
