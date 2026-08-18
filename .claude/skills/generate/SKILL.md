---
name: generate
description: "Use when someone with a saved training profile asks for a workout plan, a new training cycle, or to regenerate or adjust a plan — different exercises, skip an exercise, focus a muscle group. If no training profile exists, run /onboard first; this skill never interviews."
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "[--dataset name]"
---

Read `skills/generation/SKILL.md` and follow it exactly, then the files it points at.

That file is the source of truth and is deliberately vendor-neutral. Do not duplicate, paraphrase,
or summarise its steps here — a second copy of the flow will drift from the first.

Three bindings for this environment:

- Use `AskUserQuestion` for the pre-filled re-confirm batch (offer "same as last time" as the
  first option) and for the veto/adjust loop before writing. Free-text answers arrive through
  that tool's **Other** option. Without it, `references/rules.md` § Before writing says what to do.
- Use `Bash` for the dataset clone (`references/rules.md` § Dataset cache) and to run
  `scripts/generate.py` three times — brief, check, write (`references/rules.md` § Running the
  generator). Use `Write` for the selection file itself, to a scratch path outside `profile/`.
  If `Bash` is unavailable in this session, fall back to `references/rules.md` § No Python rather
  than choosing exercises against an unfiltered dataset.
- `--dataset` picks a non-default entry from `skills/generation/assets/datasets.json`.
