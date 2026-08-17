---
name: generation
description: "Use when someone with a saved training profile asks for a workout plan, a new training cycle, or to regenerate or adjust a plan — different exercises, skip an exercise, focus a muscle group. If no training profile exists, run onboarding first; this skill never interviews."
compatibility: "Python 3 for scripts/generate.py, and git with network access to clone the exercise dataset into datasets/."
---

# Workout plan generation

Turn a saved profile and its latest program answers into a concrete week of exercises — fitted to
the per-muscle weekly set allocation that the onboarding skill's volume model already computed —
using an exercise dataset described in `assets/datasets.json`. Written to be run by any capable
LLM agent — nothing here depends on a particular vendor, and every path below is relative to the
repository root, or to this skill's directory when it starts with `references/`, `assets/` or
`scripts/`.

## Flow

1. **Read `profile/profile.json` and find the latest program file**
   (`skills/onboarding/references/rules.md` § Finding the latest program), then check that
   program has a volume block — `references/rules.md` § Program answers and volume. No profile →
   fail loudly and point the person at the onboarding skill. Never interview here, and never
   invent a profile.
2. **Re-confirm the program answers in one pre-filled batch** — goal, days, session length,
   split, deload, shown with their saved values. Keeping all of them is one click. Any change
   goes through onboarding's update path (a new dated program file, volume recomputed there) —
   never edited in place here, and never written back silently.
3. **Read the personal rules file if one exists** — `references/rules.md` § Personal rules. Say
   which rules are active in one line before generating.
4. **Make the dataset local** — `references/rules.md` § Dataset cache. Never fabricate exercises
   when the dataset is unavailable.
5. **Run `scripts/generate.py`** — `references/rules.md` § Running the generator. If it cannot
   run in this environment, `references/rules.md` § No Python covers the fallback.
6. **Echo before writing** — the planned-versus-allocated table, the week itself, every warning,
   and the exact paths about to be written — `references/rules.md` § Before writing. A requested
   swap is a re-run with a rules change, not a hand-edit of the generator's output.
7. **Write only under `profile/plans/`** — never to `profile.json`, never under `programs/`.

**Hand-editing the rules file or a finished plan**: point the person at the repository's `docs/generation-fields.md`
and `assets/examples/rules.example.md`.

## Gotchas

Each of these has produced a wrong plan. The section named holds the detail.

- A program file without a volume block is not an invitation to estimate one — run onboarding's
  volume step first; the generator refuses without it (§ Program answers and volume).
- No dataset cache and no way to clone → stop and say so. Never generate from memory of what
  the dataset probably contains (§ Dataset cache).
- The generator will not run by hand. If it cannot execute here, write nothing and hand back
  the exact command; a missing plan is recoverable, a plausible wrong one is not (§ No Python).
- "Swap X for Y" is a rules change plus a re-run, so the volume arithmetic stays true — never
  hand-edit an exercise into the output (§ Before writing).
- `profile/rules.md` is the person's file — plain Markdown, `## Section` headings and `- item`
  bullets: read it, offer Markdown snippets for it, never write it (§ Personal rules).
- A same-day re-run gets a `-2` suffix; old plans are records, never edited or deleted
  (§ Running the generator).

Everything else — dataset descriptors, tier and muscle mappings, every tunable number, the plan
and rules contracts — lives in `assets/datasets.json`, `scripts/generate.config.json`, and
`assets/schema/*.json`. This file does not change when any of those do.
