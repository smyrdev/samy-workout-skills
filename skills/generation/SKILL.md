---
name: generation
description: "Use when someone with a saved training profile asks for a workout plan, a new training cycle, or to regenerate or adjust a plan — different exercises, skip an exercise, focus a muscle group. If no training profile exists, run onboarding first; this skill never interviews."
compatibility: "Python 3 for scripts/generate.py, and git with network access to clone the exercise dataset into datasets/."
---

# Workout plan generation

Turn a saved profile and its latest program answers into a concrete week of exercises, built
against the per-muscle weekly set allocation the onboarding skill's volume model already computed,
from an exercise dataset described in `assets/datasets.json`. The script works out the budget and
which exercises are legal; **you choose the week from what it offers**, guided by
`references/coaching.md`, and it checks the result. Paths are relative to the repository root, or
to this skill's directory when they start with `references/`, `assets/` or `scripts/`.

## Flow

1. **Read `profile/profile.json` and find the latest program file**
   (`skills/onboarding/references/rules.md` § Finding the latest program), then check it has a
   volume block — `references/rules.md` § Program answers and volume. No profile → fail loudly and
   point at the onboarding skill; never interview here, never invent a profile.
2. **Re-confirm the program answers in one pre-filled batch** — goal, days, session length,
   split, deload, with their saved values; keeping all is one click. Any change goes through
   onboarding's update path — never edited in place here, never written back silently.
3. **Read the personal rules file if one exists** — `references/rules.md` § Personal rules. Say
   which rules are active in one line.
4. **Make the dataset local** — `references/rules.md` § Dataset cache.
5. **Ask `scripts/generate.py` for a brief** — `references/rules.md` § Running the generator. It
   returns the budget and the legal candidates, and writes nothing.
6. **Choose the week from that brief** — which candidate, in what order, paired with what, at what
   effort — reading `references/coaching.md` first; `references/rules.md` § Choosing from the
   brief. Hand the choices back to the same script **without `--write` first**: it checks them
   and prints the allocated-versus-planned table and warnings, and that output is the echo
   (§ Running the generator).
7. **Echo before writing** — `references/rules.md` § Before writing.
8. **Write only under `profile/plans/`** — never to `profile.json`, never under `programs/`.

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
- "Swap X for Y" is another choice and another compose — or a rules change if it should stick —
  so the volume arithmetic stays true; never hand-edit an exercise into the written plan
  (§ Before writing).
- check first, write second. Sum sets by hand and the table will disagree with the generator's
  (indirect volume is discounted); one run did exactly that, wrote, and then wrote a second
  `-2` pair. The check run costs nothing and writes nothing (§ Running the generator).
- `profile/rules.md` is the person's file — plain Markdown, `## Section` headings and `- item`
  bullets: read it, offer Markdown snippets for it, never write it (§ Personal rules).
- A same-day re-run gets a `-2` suffix; old plans are records, never edited or deleted
  (§ Running the generator).

Everything else lives in `assets/datasets.json`, `scripts/generate.config.json`,
`assets/schema/*.json` and `references/coaching.md`; this file does not change when they do.
