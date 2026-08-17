---
name: onboarding
description: "Use when someone is setting up a training profile for the first time, says they are new here, or asks to change body stats, experience, gym, goal, days per week, session length, split, deload, benchmarks, or program name/emoji. Also use when another skill reports a training profile is missing."
compatibility: "Python 3 for scripts/volume.py; without it the skill still writes the files and hands back the command."
---

# Training profile onboarding

Interview the person and save their answers, so a workout generator can read them instead of
asking twenty questions every cycle. One repository holds one profile, at `profile/`. Written to
be run by any capable LLM agent — nothing here depends on a particular vendor, and every path
below is relative to the repository root, or to this skill's directory when it starts with
`references/`, `assets/` or `scripts/`.

## Flow

1. **Check whether `profile/profile.json` already exists** — `references/rules.md` § If a
   profile already exists. A fresh interview overwrites it; never start over on an inferred
   intent.
2. **Ask the questions in `references/questions.yaml`, in `batch` order.** Offer each entry's
   `options`; always accept a free-text answer instead (its `escape`). Store the `value`, never
   the label. Follow each entry's `notes` — that is where the validation rules live.
3. **Echo the summary and the exact paths about to be written, before writing anything** —
   `references/rules.md` § Before writing. No first-pass write without this.
4. **Save `profile.json` and `programs/program-<date>.json`**, shaped by
   `assets/schema/profile.schema.json` and `assets/schema/program.schema.json` —
   `references/rules.md` § Writing the files.
5. **Fill the volume block** by running `scripts/volume.py` against the files just written. If it
   cannot be run in this environment, `references/rules.md` § No Python covers the fallback — it
   is not a blocker.

**Updating an existing profile** instead of a fresh interview: `references/rules.md` §
Updating an existing profile.

**Hand-filled files instead of an interview**: point the person at the repository's `docs/onboarding-fields.md` and
`assets/examples/*.json`.

## Gotchas

Each of these has cost someone a profile. The section named holds the detail.

- An existing profile is not permission to overwrite it. "Set me up" from someone who has one is
  ambiguous — stop and ask (§ If a profile already exists).
- Never invent, default or clamp an answer. A skipped question is asked again; an implausible
  number is a typo until confirmed (§ Validation).
- Changing `units` converts the measurements; it never relabels them (§ Unit conversion).
- A change to any program-scope answer is a new dated file under `programs/`, never an edit of
  the old one; a profile-scope change edits `profile.json` in place (§ Updating an existing
  profile).
- Do not compute the volume block by hand when the script cannot run — leave it `null` and hand
  back the command (§ No Python).
- If the interview is abandoned before the echo step, write nothing. A partial profile is worse
  than none (§ Before writing).

Everything else — question wording, valid answers, the schema, the volume model, what the
generation skill reads — lives in `references/questions.yaml`, `references/rules.md`,
`assets/schema/*.json`, and `scripts/volume.config.json`. This file does not change when any of
those do.
