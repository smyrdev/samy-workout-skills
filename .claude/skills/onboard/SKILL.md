---
name: onboard
description: "Use when someone is setting up a training profile for the first time, says they are new here, or asks to change body stats, experience, gym, goal, days per week, session length, split, deload, benchmarks, or program name/emoji. Also use when another skill reports a training profile is missing."
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "[--update]"
---

Read `skills/onboarding/SKILL.md` and follow it exactly, then its pointers into
`references/questions.yaml`, `references/rules.md`, `assets/schema/*.json` and
`scripts/volume.config.json`.

That file is the source of truth and is deliberately vendor-neutral. Do not duplicate, paraphrase,
or summarise its steps here — a second copy of the flow will drift from the first.

Three bindings for this environment:

- Use `AskUserQuestion` wherever `references/questions.yaml` offers `options`, batching as
  `SKILL.md`'s Flow section describes. Each question's `escape` is the **Other** option, which
  that tool always provides.
- Run `scripts/volume.py` with the `Bash` tool for the fill-the-volume-block step. If `Bash` is
  unavailable in this session, fall back to `references/rules.md` § No Python rather than
  computing it by hand.
- `--update` means go to `references/rules.md` § Updating an existing profile instead of the full
  interview.
