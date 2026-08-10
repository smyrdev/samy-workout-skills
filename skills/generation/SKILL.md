---
name: generation
description: "Use when someone with a saved training profile asks for a workout plan, a new training cycle, or to regenerate or adjust a plan — different exercises, skip an exercise, focus a muscle group. If no training profile exists, run onboarding first; this skill never interviews."
---

# Workout plan generation

Turn a saved profile and its latest program answers into a concrete week of exercises — fitted to
the per-muscle weekly set allocation that the onboarding skill's volume model already computed —
using an exercise dataset described in `datasets.json`. Written to be run by any capable LLM
agent — nothing here depends on a particular vendor, and every path below is relative to the
repository root.

## Flow

1. **Read `profile/profile.json` and find the latest program file**
   (`skills/onboarding/rules.md` § Finding the latest program), then check that program has a
   volume block — `rules.md` § Program answers and volume. No profile → fail loudly and point the
   person at the onboarding skill. Never interview here, and never invent a profile.
2. **Re-confirm the program answers in one pre-filled batch** — goal, days, session length,
   split, deload, shown with their saved values. Keeping all of them is one click. Any change
   goes through onboarding's update path (a new dated program file, volume recomputed there) —
   never edited in place here, and never written back silently.
3. **Read the personal rules file if one exists** — `rules.md` § Personal rules. Say which rules
   are active in one line before generating.
4. **Make the dataset local** — `rules.md` § Dataset cache. Never fabricate exercises when the
   dataset is unavailable.
5. **Run `scripts/generate.py`** — `rules.md` § Running the generator. If it cannot run in this
   environment, `rules.md` § No Python covers the fallback.
6. **Echo before writing** — the planned-versus-allocated table, the week itself, every warning,
   and the exact paths about to be written — `rules.md` § Before writing. A requested swap is a
   re-run with a rules change, not a hand-edit of the generator's output.
7. **Write only under `profile/plans/`** — never to `profile.json`, never under `programs/`.

**Hand-editing the rules file or a finished plan**: point the person at `FIELDS.md` and
`examples/rules.example.json`.

Everything else — dataset descriptors, tier and muscle mappings, every tunable number, the plan
and rules contracts — lives in `datasets.json`, `scripts/generate.config.json`, and
`schema/*.json`. This file does not change when any of those do.
