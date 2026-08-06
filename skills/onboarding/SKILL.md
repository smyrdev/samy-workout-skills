---
name: onboarding
description: "Use when someone is setting up a training profile for the first time, says they are new here, or asks to change body stats, experience, gym, goal, days per week, session length, split, deload, benchmarks, or program name/emoji. Also use when another skill reports a training profile is missing."
---

# Training profile onboarding

Interview one person and save their answers, so a workout generator can read them instead of
asking twenty questions every cycle. Written to be run by any capable LLM agent — nothing here
depends on a particular vendor, and every path below is relative to the repository root.

## Flow

1. **Resolve whose profile this is** — `rules.md` § Resolving a profile. Stop and ask before
   assuming; there is no default profile and no last-used memory.
2. **Ask the questions in `questions.yaml`, in `batch` order.** Offer each entry's `options`;
   always accept a free-text answer instead (its `escape`). Store the `value`, never the label.
   Follow each entry's `notes` — that is where the validation rules live.
3. **Echo the summary and the exact paths about to be written, before writing anything** —
   `rules.md` § Before writing. No first-pass write without this.
4. **Save `profile.json` and `programs/program-<date>.json`**, shaped by `schema/profile.schema.json`
   and `schema/program.schema.json` — `rules.md` § Writing the files.
5. **Fill the volume block** by running `scripts/volume.py` against the files just written. If it
   cannot be run in this environment, `rules.md` § No Python covers the fallback — it is not a
   blocker.

**Updating an existing profile** instead of a fresh interview: `rules.md` §
Updating an existing profile.

**Hand-filled files instead of an interview**: point the person at `FIELDS.md` and
`examples/*.json`.

Everything else — question wording, valid answers, the schema, the volume model, what a future
generation skill reads — lives in `questions.yaml`, `rules.md`, `schema/*.json`, and
`scripts/volume.config.json`. This file does not change when any of those do.
