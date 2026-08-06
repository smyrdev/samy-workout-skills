---
name: generate
description: "Use when someone with a saved training profile asks for a workout plan, a new training cycle, or to regenerate or adjust a plan — different exercises, skip an exercise, focus a muscle group. If no training profile exists, run /onboard first; this skill never interviews."
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "[name] [--dataset name]"
---

Read `skills/generation/SKILL.md` and follow it exactly, then its pointers into `rules.md`,
`datasets.json`, `schema/*.json` and `scripts/generate.config.json`.

That file is the source of truth and is deliberately vendor-neutral. Do not duplicate, paraphrase,
or summarise its steps here — a second copy of the flow will drift from the first.

Three bindings for this environment:

- Use `AskUserQuestion` for step 3 (the pre-filled re-confirm batch — offer "same as last time"
  as the first option) and for the veto/adjust loop in step 7. Free-text answers arrive through
  that tool's **Other** option.
- Use `Bash` for the dataset clone (`rules.md` § Dataset cache) and to run
  `scripts/generate.py` (`rules.md` § Running the generator). If `Bash` is unavailable in this
  session, fall back to `rules.md` § No Python rather than fitting exercises by hand.
- A bare name argument selects the profile (`/generate sara`). `--dataset` picks a non-default
  entry from `skills/generation/datasets.json`.
