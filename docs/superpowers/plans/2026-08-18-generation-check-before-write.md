# Generation Check-Before-Write Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "compose without `--write`" the documented, visible middle step of the generation flow, so the agent shows the generator's own planned-vs-allocated table before any plan file lands.

**Architecture:** No restructuring. `generate.py` gains one function, `print_check(plan)`, that writes a compact table + warnings to stderr on every `--selection` run; stdout is untouched. `references/rules.md` documents three commands (brief → check → write), `SKILL.md` step 6 and a new gotcha point at it, `docs/generation.md` names the step. One offline test case pins the behaviour.

**Tech Stack:** Python 3 (stdlib only), bash test suite in `tests/skills/`, `python scripts/validate-skills.py`.

**Spec:** `docs/superpowers/specs/2026-08-18-generation-check-before-write-design.md`

## Global Constraints

- Soft fix: no new flags, no new refusals. `generate.py` still refuses exactly two things (an exercise it never offered, a rep target under the floor) plus its existing usage/input errors.
- stdout of every existing invocation is byte-for-byte unchanged; the new output goes to **stderr** only.
- Every tunable number stays in `scripts/generate.config.json`; this change introduces none.
- `skills/generation/SKILL.md` stays portable: no vendor tool names, no absolute paths, skill-root-relative pointers.
- Before each commit: `python scripts/validate-skills.py` exits 0 and `bash tests/skills/run-skill-tests.sh` passes.
- Commit messages: no `Claude-Session` trailer (repo convention).
- Test runner note: `run_generate` in `tests/skills/test-generation-script.sh` captures stdout **and** stderr into `$out` (`2>&1`). Existing assertions are `grep`-based, so extra stderr lines do not break them; only `--brief` runs are saved to files as JSON, and those print no table.

---

### Task 1: `generate.py` prints the check table to stderr on every `--selection` run

**Files:**
- Modify: `skills/generation/scripts/generate.py` (add `print_check` near `render_markdown` at ~line 713; call it in `main()` right after `compose_plan(...)`, ~line 1086)
- Test: `tests/skills/test-generation-script.sh` (new block after "Without --write the plan goes to stdout", ~line 179)

**Interfaces:**
- Consumes: the `plan` dict returned by `compose_plan()`. Relevant shape: `plan["targets"]` is `{group: {"allocated": int, "planned": float}}` in canonical group order; `plan["warnings"]` is a list of strings such as `"short:hamstrings"`.
- Produces: `print_check(plan, stream=sys.stderr) -> None`. Output format (exact):

```
check: allocated vs planned (generator's numbers — show this before writing)
  muscle       allocated  planned
  chest               14     13.0
  back                17     16.5   short
  ...
  warnings: short:back
```
  When there are no warnings the last line is `  warnings: none`. The `short` marker appears on a row iff `f"short:{group}"` is in `plan["warnings"]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/skills/test-generation-script.sh`, immediately after the `echo ""` that closes the "Without --write the plan goes to stdout" block (after `first="$out"`):

```bash
echo "The check step: a selection without --write shows the table and writes nothing"
CHECK_DIR="$PROJECT/check-plans"
mkdir -p "$CHECK_DIR"
run_default
assert_exit_code 0 "$code" "composing without --write succeeds"
assert_contains "$out" "check: allocated vs planned" "prints the check header"
for group in chest back shoulders biceps triceps quads hamstrings glutes calves core; do
    assert_contains "$out" "^  $group " "the check table has a $group row"
done
assert_contains "$out" "warnings: none" "says when there is nothing to warn about"
assert_file_absent "$CHECK_DIR/plan.json" "the check step writes no plan"
if [ -z "$(ls -A "$CHECK_DIR")" ]; then
    _pass "the check step leaves the plans directory empty"
else
    _fail "the check step leaves the plans directory empty"
fi
# The table is stderr, so a caller redirecting stdout to a file still sees it.
stdout_only=$(PYTHONIOENCODING=utf-8 python "$GENERATE" --profile "$PROFILE" --program "$PROGRAM" \
    --dataset-dir "$PROJECT" --today "$TODAY" --selection "$SELECTION" 2>/dev/null)
assert_not_contains "$stdout_only" "check: allocated vs planned" "the table is not on stdout"
assert_contains "$stdout_only" '"sessions"' "stdout is still the plan JSON"
echo ""
```

Note: `assert_contains` uses `grep -qi "$pattern"`, so `"^  chest "` is a valid anchored regex; `_pass`/`_fail` are the helpers' internal reporters and are already used directly elsewhere in this file (see the "Determinism" block).

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-script.sh`
Expected: FAIL on "prints the check header" and every "has a … row" assertion; the file-absence assertions pass (nothing has changed there yet).

- [ ] **Step 3: Implement `print_check`**

In `skills/generation/scripts/generate.py`, directly **before** `def render_markdown(plan):` add:

```python
def print_check(plan, stream=None):
    """The check step. Every --selection run prints the generator's own
    allocated-versus-planned numbers and warnings to stderr, so the coach shows
    this table — never a hand tally — before deciding to write. stdout is left
    alone: it still carries the plan JSON, or the `wrote …` lines."""
    stream = stream if stream is not None else sys.stderr
    warnings = plan.get("warnings", [])
    short = {w.split(":", 1)[1] for w in warnings if w.startswith("short:")}
    print("check: allocated vs planned (generator's numbers — show this before writing)",
          file=stream)
    print(f"  {'muscle':<12}{'allocated':>10}{'planned':>9}", file=stream)
    for group, row in plan["targets"].items():
        marker = "   short" if group in short else ""
        print(f"  {group:<12}{row['allocated']:>10}{row['planned']:>9.1f}{marker}", file=stream)
    print("  warnings: " + (", ".join(warnings) if warnings else "none"), file=stream)
```

Then in `main()`, right after

```python
    plan = compose_plan(ctx, selection, brief, config, today,
                        commit=dataset_commit(dataset_dir))
```

add one line:

```python
    print_check(plan)
```

(before the `out = Path(args.write) …` block, so the table appears whether or not the run goes on to write).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-script.sh`
Expected: PASS, including the pre-existing "Without --write", "Determinism", "Plans are never overwritten" and "A shortfall is never hidden" blocks (the shortfall block already asserts `short:hamstrings` in `$out`; it now also appears in the table's warnings line — still a pass).

Also run: `python skills/generation/scripts/generate.py --self-test` → exit 0 (self-test never calls `main()`, so it is unaffected; this just confirms nothing else moved).

- [ ] **Step 5: Run the full offline suite and validator**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh`
Expected: validator exit 0, suite `Passed: 7  Failed: 0`.

- [ ] **Step 6: Commit**

```bash
git add skills/generation/scripts/generate.py tests/skills/test-generation-script.sh
git commit -m "generate.py: print the check table to stderr on every --selection run"
```

---

### Task 2: `references/rules.md` documents three commands — brief, check, write

**Files:**
- Modify: `skills/generation/references/rules.md` § "Running the generator" (starts ~line 58; the block from `Two commands.` through `never in prose.`)
- Test: `tests/skills/test-generation-skill.sh` (policy pins; add two assertions to the existing "references/rules.md keeps the four things shown before any file lands" block, ~line 111)

**Interfaces:**
- Produces: the phrases `## Running the generator`, `Three commands`, and `never a hand tally` in `rules.md`, which Task 3's SKILL.md gotcha and Task 4's docs refer to by section name.

- [ ] **Step 1: Write the failing policy test**

In `tests/skills/test-generation-skill.sh`, inside the block that begins `echo "references/rules.md keeps the four things shown before any file lands"`, add after the last `assert_file_contains "$RULES" …` line of that block:

```bash
assert_file_contains "$RULES" "Three commands" "documents brief, check, write as three commands"
assert_file_contains "$RULES" "never a hand tally" "the planned column is the generator's number"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-skill.sh`
Expected: FAIL on both new assertions.

- [ ] **Step 3: Rewrite the section**

In `skills/generation/references/rules.md`, replace the paragraph `Two commands. The first asks what the week may contain; the second says what it will.` and the two code blocks + the paragraph between them (up to and including the sentence ending `never in prose.`) with:

````markdown
Three commands. The first asks what the week may contain; the second says what the chosen week
delivers, without writing; the third writes it.

```
python skills/generation/scripts/generate.py --brief \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name>
```

That prints the budget and the candidate pools, and writes nothing. Choose from it —
[Choosing from the brief](#choosing-from-the-brief) — then hand the choices back **without**
`--write`:

```
python skills/generation/scripts/generate.py \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --selection <selection>.json
```

This is the check. It composes the week, prints the plan JSON to stdout and, on stderr, the
allocated-versus-planned table with every warning. That table is what the echo step shows —
[Before writing](#before-writing) — and the planned column is the generator's number, never a
hand tally: indirect volume is discounted, and a coach's sum will disagree with the script's.
If a target is short or a choice looks wrong, change the selection and run the check again;
nothing has been written yet.

Only when the person has seen it and not vetoed, run the same command once more with the
outputs added:

```
python skills/generation/scripts/generate.py \
  --profile profile/profile.json \
  --program profile/programs/program-<date>.json \
  --dataset-dir datasets/<name> \
  --selection <selection>.json \
  --write profile/plans/plan-<today>.json \
  --write-md profile/plans/plan-<today>.md
```

Add `--rules profile/rules.md` to all three when it exists. If today's filename is taken,
suffix `-2`, then `-3` — the generator refuses to overwrite a plan, and so does this skill; old
plans are records, never edited or deleted. The selection file is working material, not a record:
it belongs in a scratch location, never under `profile/`. Everything tunable lives in
`scripts/generate.config.json`, never in the script and never in prose.
````

Keep everything else in the file as it is. Check the "Before writing" section (~line 112) still reads correctly — it does not need edits; its bullet "The **planned-versus-allocated table**" now has a source.

- [ ] **Step 4: Run tests and validator**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh --test test-generation-skill.sh`
Expected: validator exit 0; policy test PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/generation/references/rules.md tests/skills/test-generation-skill.sh
git commit -m "rules.md: the generator runs three times — brief, check, write"
```

---

### Task 3: `SKILL.md` step 6 and a new gotcha point at the check step

**Files:**
- Modify: `skills/generation/SKILL.md` (Flow step 6, ~line 25; Gotchas list, ~line 36)
- Test: `tests/skills/test-generation-skill.sh` (the "SKILL.md stays a set of pointers" block, ~line 49)

**Interfaces:**
- Consumes: section name `§ Running the generator` from Task 2.

- [ ] **Step 1: Write the failing policy test**

In `tests/skills/test-generation-skill.sh`, in the block beginning `echo "SKILL.md stays a set of pointers"`, add after `assert_file_contains "$SKILL" "scripts/generate.py" "points at the generator"`:

```bash
assert_file_contains "$SKILL" "without \`--write\` first" "the flow checks before it writes"
assert_file_contains "$SKILL" "check first, write second" "the gotcha names the order"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-skill.sh`
Expected: FAIL on both new assertions.

- [ ] **Step 3: Edit SKILL.md**

Replace step 6 of the Flow:

```markdown
6. **Choose the week from that brief** — which candidate, in what order, paired with what, at what
   effort — reading `references/coaching.md` first; `references/rules.md` § Choosing from the
   brief. Hand the choices back to the same script to be checked, rendered and written.
```

with:

```markdown
6. **Choose the week from that brief** — which candidate, in what order, paired with what, at what
   effort — reading `references/coaching.md` first; `references/rules.md` § Choosing from the
   brief. Hand the choices back to the same script **without `--write` first**: it checks them
   and prints the allocated-versus-planned table and warnings, and that output is the echo
   (§ Running the generator).
```

Then add a new bullet to the Gotchas list, directly after the bullet that begins `- "Swap X for Y" is another choice and another compose`:

```markdown
- Check first, write second. Sum sets by hand and the table will disagree with the generator's
  (indirect volume is discounted); one run did exactly that, wrote, and then wrote a second
  `-2` pair. The check run costs nothing and writes nothing (§ Running the generator).
```

Portability check: no tool names, no absolute paths, both pointers name *when* to read (unchanged style).

- [ ] **Step 4: Run tests and validator**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh --test test-generation-skill.sh`
Expected: both clean. (`validate-skills.py` checks SKILL.md frontmatter, portability and pointer targets — the new text adds no paths.)

- [ ] **Step 5: Commit**

```bash
git add skills/generation/SKILL.md tests/skills/test-generation-skill.sh
git commit -m "SKILL.md: hand the selection back without --write first; check before write gotcha"
```

---

### Task 4: `docs/generation.md` names the check step

**Files:**
- Modify: `docs/generation.md` § "The brief and the selection" (~line 111, the paragraph beginning `Then \`--selection\` takes the choices back`)

**Interfaces:** none (prose only).

- [ ] **Step 1: Edit the paragraph**

Replace:

```markdown
Then `--selection` takes the choices back and recomputes everything: what the week delivers per
muscle against what was allocated, with any shortfall reported in `warnings` — never silently
absorbed.
```

with:

```markdown
Then `--selection` takes the choices back and recomputes everything: what the week delivers per
muscle against what was allocated, with any shortfall reported in `warnings` — never silently
absorbed. Run without `--write` this is the **check**: the plan JSON goes to stdout and the
allocated-versus-planned table with the warnings goes to stderr, so the coach shows the
generator's numbers before anything is written. The same command with `--write`/`--write-md`
is the write; nothing about the arithmetic changes between the two.
```

- [ ] **Step 2: Validate and run the suite**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh`
Expected: validator exit 0; `Passed: 7  Failed: 0`.

- [ ] **Step 3: Commit**

```bash
git add docs/generation.md
git commit -m "docs: name the check step between brief and write"
```

---

### Task 5: Re-run generation eval case 1 and record iteration-2 grades

**Files:**
- Uses: `skills/onboarding-workspace/run-eval.sh` (existing, gitignored runner from the 2026-08-17 eval run)
- Create: `skills/generation-workspace/iteration-2/GRADES.md` (gitignored)

**Interfaces:**
- Consumes: the runner's usage `bash skills/onboarding-workspace/run-eval.sh <skill> <id> <out-dir>`, run from the repo root. It clones **HEAD**, so Tasks 1–4 must be committed first.

- [ ] **Step 1: Run generation cases 1 and 3**

From the repo root:

```bash
mkdir -p skills/generation-workspace/iteration-2
for id in 1 3; do
  timeout -k 10 900 bash skills/onboarding-workspace/run-eval.sh generation $id \
    skills/generation-workspace/iteration-2/case-$id > skills/generation-workspace/iteration-2/case-$id.log 2>&1 &
done
wait
```

Expected: both `case-*/DONE` files exist; `case-*/turn1.txt` non-empty.

- [ ] **Step 2: Grade against `skills/generation/evals/evals.json`**

For case 1, check specifically (the two that failed in iteration 1):
- `ls skills/generation-workspace/iteration-2/case-1/clone/profile/plans/` → exactly one `.json` and one `.md`.
- In the transcript (`~/.claude/projects/*generation-workspace-iteration-2-case-1-clone/<session_id>.jsonl`, session id from `turn1.json`), the first `generate.py` invocation with `--selection` has no `--write`, an assistant text turn containing the table follows it, and only then a `--write` run occurs.

For case 3: unchanged assertions; confirm still 6/6.

Write `skills/generation-workspace/iteration-2/GRADES.md` in the same table format as `skills/onboarding-workspace/iteration-1/GRADES.md`, with a one-line delta per assertion versus iteration 1.

- [ ] **Step 3: Report**

No commit (workspace is gitignored). Report the two grade tables and, if case 1 still writes before showing, quote the transcript turn where it happened — that becomes the input to backlog item 3 (headless turn-boundary binding), not a reason to add a gate here.

---

## Self-review

- Spec §1 (rules.md three commands) → Task 2. §2 (SKILL.md step 6 + gotcha) → Task 3. §3 (stderr table, no flags) → Task 1. §4 (offline test) → Task 1 step 1. §5 (docs/generation.md) → Task 4. Out-of-scope items untouched. Eval re-run is not in the spec but is the acceptance check for the whole change → Task 5, marked non-committing.
- Names used consistently: `print_check(plan, stream=None)`; header string `check: allocated vs planned` appears identically in Task 1 code and test; section name `§ Running the generator` matches the existing heading in rules.md.
- Constraint check: no new flags, no new refusals, stdout unchanged (Task 1 asserts it), no numbers added to config or prose.
