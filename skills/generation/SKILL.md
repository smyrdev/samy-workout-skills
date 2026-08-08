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

1. **Resolve whose plan this is** — exactly as onboarding does it:
   `skills/onboarding/rules.md` § Resolving a profile. No profile → fail loudly and point the
   person at the onboarding skill. Never interview here, and never invent a profile.
2. **Find the latest program file** (`skills/onboarding/rules.md` § Finding the latest program)
   and check it has a volume block — `rules.md` § Program answers and volume.
3. **Re-confirm the program answers in one pre-filled batch** — goal, days, session length,
   split, style, deload, shown with their saved values. Keeping all of them is one click. Any change
   goes through onboarding's update path (a new dated program file, volume recomputed there) —
   never edited in place here, and never written back silently.
4. **Read the personal rules file if one exists** — `rules.md` § Personal rules. Say which rules
   are active in one line before generating.
5. **Make the dataset local** — `rules.md` § Dataset cache. Never fabricate exercises when the
   dataset is unavailable.
6. **Run `scripts/generate.py`** — `rules.md` § Running the generator. If it cannot run in this
   environment, `rules.md` § No Python covers the fallback.
7. **Review the plan as a coach** — `rules.md` § Reviewing the plan. Read the rules file's
   `notes` and anything the person asked this cycle; revise within the allowed list — reorder,
   swap, adjust sets, pair supersets, move between same-focus days — and record every change as a
   plain-English line in the plan's `revisions`. An untouched plan is a fine outcome: then
   `revisions` is simply absent.
8. **Echo before writing** — the volume table, the week as it stands after review, each revision
   and why, every warning, and the exact paths about to be written — `rules.md` § Before writing.
   A further swap here is another recorded revision (re-check it the same way); a lasting
   preference is a `rules.json` snippet to offer.
9. **Write only under `profiles/<slug>/plans/`** — never to `profile.json`, never under
   `programs/`, never to another person's directory. The `.md` render must describe the same week
   as the `.json`, including revisions and supersets.

**Hand-editing the rules file or a finished plan**: point the person at `FIELDS.md` and
`examples/rules.example.json`.

Everything else — dataset descriptors, tier and muscle mappings, every tunable number, the plan
and rules contracts — lives in `datasets.json`, `scripts/generate.config.json`, and
`schema/*.json`. This file does not change when any of those do.
