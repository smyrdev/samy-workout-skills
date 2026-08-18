# Generation Echo-Is-A-Stop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generation echo an explicit turn boundary so a headless or tool-less session shows the plan and stops instead of writing in the same turn.

**Architecture:** Prose only. Two sentences appended to `references/rules.md` § Before writing (portable, harness-independent); one clause each in the wrapper's `AskUserQuestion` and `Bash` bullets; three policy pins. Then one eval re-run as acceptance.

**Tech Stack:** Markdown, bash policy tests, `python scripts/validate-skills.py`.

**Spec:** `docs/superpowers/specs/2026-08-18-generation-echo-is-a-stop-design.md`

## Global Constraints

- Lean: rules.md gains exactly the two sentences quoted below; the wrapper gains exactly the clauses quoted below. No other prose changes.
- `.claude/skills/generate/SKILL.md` keeps exactly three bindings (policy test pins "Three bindings").
- The portable `skills/generation/SKILL.md` is not touched.
- Before each commit: `python scripts/validate-skills.py` exit 0; `bash tests/skills/run-skill-tests.sh` → Passed 7, Failed 0.
- Commit messages: no `Claude-Session` trailer.

---

### Task 1: rules.md — the echo ends the turn; wrapper — tool-less fallback and "three times"

**Files:**
- Modify: `skills/generation/references/rules.md` § Before writing (last paragraph, ends "If they abandon here, write nothing.")
- Modify: `.claude/skills/generate/SKILL.md` (bullets 1 and 2 under "Three bindings for this environment")
- Test: `tests/skills/test-generation-skill.sh` (blocks "references/rules.md keeps the four things shown before any file lands" and "The wrapper is a pointer, not a fork")

**Interfaces:** none.

- [ ] **Step 1: Write the failing policy pins**

In `tests/skills/test-generation-skill.sh`, inside the block that begins `echo "references/rules.md keeps the four things shown before any file lands"`, after the line `assert_file_contains "$RULES" "If they abandon here, write nothing." ...`, add:

```bash
assert_file_contains "$RULES" "The echo ends the turn" "the echo is a turn boundary"
```

Inside the block that begins `echo "The wrapper is a pointer, not a fork"`, after `assert_file_contains "$WRAPPER" "scripts/generate.py" "binds the generator step"`, add:

```bash
assert_file_contains "$WRAPPER" "three times" "runs the generator three times: brief, check, write"
assert_file_contains "$WRAPPER" "stop after the echo" "binds the no-question-tool fallback to a stop"
```

- [ ] **Step 2: Run to verify they fail**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-skill.sh`
Expected: FAIL on the three new assertions only.

- [ ] **Step 3: Edit rules.md**

In `skills/generation/references/rules.md` § Before writing, the last paragraph currently ends:

```
never hand-edit an exercise into the generator's output. If they abandon here, write nothing.
```

Append two sentences so the paragraph ends:

```
never hand-edit an exercise into the generator's output. If they abandon here, write nothing.
The echo ends the turn: write only after they answer, in a later turn. With no way to ask (no
question tool, a non-interactive session), show the same four things as text and stop.
```

Rewrap to the file's ~98-column width; keep "The echo ends the turn" on one line.

- [ ] **Step 4: Edit the wrapper**

In `.claude/skills/generate/SKILL.md` replace the first two bullets under "Three bindings for this environment:" with:

```markdown
- Use `AskUserQuestion` for the pre-filled re-confirm batch (offer "same as last time" as the
  first option) and for the veto/adjust loop before writing. Free-text answers arrive through
  that tool's **Other** option. If that tool is unavailable, keep the saved answers, say so in a
  line, and stop after the echo (`references/rules.md` § Before writing).
- Use `Bash` for the dataset clone (`references/rules.md` § Dataset cache) and to run
  `scripts/generate.py` three times — brief, check, write (`references/rules.md` § Running the
  generator). Use `Write` for the selection file itself, to a scratch path outside `profile/`.
  If `Bash` is unavailable in this session, fall back to `references/rules.md` § No Python rather
  than choosing exercises against an unfiltered dataset.
```

The third bullet (`--dataset`) is unchanged.

- [ ] **Step 5: Run tests and validator**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh`
Expected: exit 0; Passed 7, Failed 0.

- [ ] **Step 6: Commit**

```bash
git add skills/generation/references/rules.md .claude/skills/generate/SKILL.md tests/skills/test-generation-skill.sh
git commit -m "Generation: the echo ends the turn; wrapper binds the no-question-tool fallback and the three generator runs"
```

---

### Task 2: Acceptance — re-run generation eval case 1, record iteration-3 grades

**Files:**
- Uses: `skills/onboarding-workspace/run-eval.sh` (gitignored runner; clones HEAD — Task 1 must be committed)
- Create: `skills/generation-workspace/iteration-3/GRADES.md` (gitignored)

- [ ] **Step 1: Run**

From the repo root:

```bash
mkdir -p skills/generation-workspace/iteration-3
timeout -k 10 900 bash skills/onboarding-workspace/run-eval.sh generation 1 \
  skills/generation-workspace/iteration-3/case-1 > skills/generation-workspace/iteration-3/case-1.log 2>&1
```

Expected: `case-1/DONE` exists; `turn1.txt` non-empty; `turn2.txt` exists (the runner sends a follow-up when turn 1 ends on a question).

- [ ] **Step 2: Grade**

Against `skills/generation/evals/evals.json` generation case 1 (7 assertions). Specifically: in the transcript (`~/.claude/projects/*generation-workspace-iteration-3-case-1-clone/<session_id>.jsonl`, id from `turn1.json`), list in order every Bash tool_use with `generate.py` (note `--selection` / `--write` presence) and every assistant text containing "allocated"/"planned"/"profile/plans/"; the required order is: check run (no `--write`) → assistant text with table + both paths → *end of turn 1* → `--write` run in turn 2. Also: exactly one `.json` + `.md` pair under `clone/profile/plans/`; fixtures byte-identical (`cmp` against `skills/generation/evals/files/`); plan validates (use `validate_instance` from `scripts/validate-skills.py` via importlib; set `PYTHONUTF8=1`).

- [ ] **Step 3: Record**

Write `skills/generation-workspace/iteration-3/GRADES.md` in the shape of `skills/generation-workspace/iteration-2/GRADES.md`, with a per-assertion delta vs iteration 2. No commit.

---

## Self-review

- Spec §1 → Task 1 step 3; §2 → step 4; §3 → step 1; §4 → Task 2. Constraints: three bindings kept (bullets edited in place), portable SKILL.md untouched, quoted text is the only prose change.
- Pinned strings match between plan text and tests: "The echo ends the turn", "three times", "stop after the echo".
