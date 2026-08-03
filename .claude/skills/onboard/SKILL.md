---
name: onboard
description: >
  Use when someone is setting up a training profile for the first time, says they are new here, or
  asks to change their body stats, bodyfat, lifting or cardio experience, gym type, training goal,
  days per week, session length, split preference, deload preference, strength benchmarks, or
  program name. Also use when another skill reports that a training profile is missing.
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "[name] [--update]"
---

Read `skills/onboarding/SKILL.md` and follow it exactly.

That file is the source of truth and is deliberately vendor-neutral. Do not duplicate, paraphrase,
or summarise its steps here — a second copy of the flow will drift from the first.

Two bindings for this environment:

- Use `AskUserQuestion` wherever it says to offer choices, batching as its Flow section describes.
  Its "free-text escape" is the **Other** option, which that tool always provides.
- A bare name argument selects the profile (`/onboard sara`). `--update` means go to its
  **Updating** section instead of the full interview.
