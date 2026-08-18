# Generation: the echo is a stop

**Problem.** Eval iteration 2 (generation case 1): the agent ran the check correctly, then wrote in
the same turn — "I'll write the plan now and present the echo alongside it" — because the session had
no interactive question tool. The rules say "let the person veto"; nothing says the echo *ends the
turn*, so with no way to ask, the agent rationalised past the veto. Onboarding, whose rules end the
turn on the read-back, passed the same headless harness.

**Fix.** Two sentences in the portable rules; one clause in each of two wrapper bullets. Lean on
purpose — both files are context-heavy.

## Changes

1. `skills/generation/references/rules.md` § Before writing — append to the last paragraph, after
   "If they abandon here, write nothing.":
   > The echo ends the turn: write only after they answer, in a later turn. With no way to ask
   > (no question tool, a non-interactive session), show the same four things as text and stop.
2. `.claude/skills/generate/SKILL.md` —
   - `AskUserQuestion` bullet, appended clause: "If that tool is unavailable, keep the saved
     answers, say so in a line, and stop after the echo (`references/rules.md` § Before writing)."
   - `Bash` bullet: "run `scripts/generate.py` twice — once for the brief, once with the selection"
     → "run `scripts/generate.py` three times — brief, check, write". Still three bindings.
3. `tests/skills/test-generation-skill.sh` — pins: rules.md contains "The echo ends the turn";
   wrapper contains "three times" and "stop after the echo".
4. Acceptance: re-run generation eval case 1 (runner in `skills/onboarding-workspace/run-eval.sh`);
   the two remaining assertions — table shown and paths named before any write — should hold via
   the runner's follow-up turn. Record iteration-3 grades (gitignored).

## Out of scope

Script changes; onboarding wrapper; the portable `SKILL.md` (step 7 already points at § Before
writing).
