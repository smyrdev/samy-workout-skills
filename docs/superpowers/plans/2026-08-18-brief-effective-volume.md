# Brief Effective-Volume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every brief candidate carries `effective_volume` — the post-discount per-muscle credit the generator will actually count — beside the raw `volume` map, so a coach's arithmetic matches the check table.

**Architecture:** `prepare()` already computes `row["effective"]`; `rank_candidates` just emits it. One self-test invariant and one CLI test pin the equality against `config["indirect_discount"]`. Three one-line doc corrections say which column to sum.

**Tech Stack:** Python 3 stdlib, bash test suite, `python scripts/validate-skills.py`.

**Spec:** `docs/superpowers/specs/2026-08-18-brief-effective-volume-design.md`

## Global Constraints

- No arithmetic is added or changed: `effective_volume` is exactly the existing `row["effective"]`.
- No literal discount value (0.5, 0.25) appears in tests or prose as a rule; tests read `config["indirect_discount"]`. (`docs/generation.md` may keep its existing "default half — so 0.5 counts 0.25" illustration; it already says "default".)
- The plan JSON shape is unchanged. `rules.md` and both `SKILL.md` files are untouched.
- Before each commit: `python scripts/validate-skills.py` exit 0; `bash tests/skills/run-skill-tests.sh` → Passed 7, Failed 0.
- Commit messages: no `Claude-Session` trailer.

---

### Task 1: `effective_volume` in the brief, pinned by self-test and CLI test

**Files:**
- Modify: `skills/generation/scripts/generate.py` — `rank_candidates` (~line 447–469) and `run_self_test` (add after invariant "2. The budget is a ceiling…", ~line 902)
- Test: `tests/skills/test-generation-script.sh` — block "The brief is the half that stays reproducible" (~line 460–474)

**Interfaces:**
- Produces: each brief candidate has `"effective_volume": {group: float}` with the same keys as `"volume"`.

- [ ] **Step 1: Write the failing CLI test**

In `tests/skills/test-generation-script.sh`, after `assert_file_contains "$PROJECT/brief-a.json" '"candidates"' "offers candidates"`, add:

```bash
assert_file_contains "$PROJECT/brief-a.json" '"effective_volume"' "each candidate says what it will actually count"
if PYTHONUTF8=1 python - "$PROJECT/brief-a.json" "$CONFIG" <<'PY'
import json, sys
brief = json.load(open(sys.argv[1], encoding="utf-8"))
discount = json.load(open(sys.argv[2], encoding="utf-8"))["indirect_discount"]
for pool in brief["candidates"].values():
    for c in pool:
        raw, eff = c["volume"], c["effective_volume"]
        assert set(raw) == set(eff), (c["name"], "key sets differ")
        for g, v in raw.items():
            want = v if v >= 1.0 else v * discount
            assert abs(eff[g] - want) < 1e-9, (c["name"], g, eff[g], want)
PY
then
    _pass "effective_volume is the raw map with the config's indirect discount applied"
else
    _fail "effective_volume is the raw map with the config's indirect discount applied"
fi
```

(`$CONFIG` is already defined at the top of the file as the path to `generate.config.json`.)

- [ ] **Step 2: Run to verify it fails**

Run: `bash tests/skills/run-skill-tests.sh --test test-generation-script.sh`
Expected: FAIL on "each candidate says what it will actually count" and on the python assertion block (KeyError → non-zero → `_fail`).

- [ ] **Step 3: Emit the key**

In `rank_candidates`, in the dict literal, directly after `"volume": r["muscles"],` add:

```python
            "effective_volume": r["effective"],
```

- [ ] **Step 4: Add the self-test invariant**

In `run_self_test`, after the block commented `# 2. The budget is a ceiling, and every target group has something to offer.` (ends with the `check(all(brief["candidates"][g] ...` call), add:

```python
    # 2b. What the coach is told each candidate is worth is what the generator
    # will count: raw coefficients at or above 1.0 pass through, everything
    # under counts at the config's indirect discount. Same key set, no more.
    discount = config["indirect_discount"]
    for pool in brief["candidates"].values():
        for c in pool:
            raw, eff = c["volume"], c["effective_volume"]
            check(set(raw) == set(eff), f"{c['name']}: effective_volume keys differ from volume")
            check(all(abs(eff[g] - (v if v >= 1.0 else v * discount)) < 1e-9
                      for g, v in raw.items()),
                  f"{c['name']}: effective_volume does not apply indirect_discount")
```

- [ ] **Step 5: Run tests, self-test, validator**

Run: `python skills/generation/scripts/generate.py --self-test` → `OK: … all invariant groups hold`
Run: `bash tests/skills/run-skill-tests.sh --test test-generation-script.sh` → PASS
Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh` → exit 0; Passed 7, Failed 0.

- [ ] **Step 6: Commit**

```bash
git add skills/generation/scripts/generate.py tests/skills/test-generation-script.sh
git commit -m "Brief: each candidate carries effective_volume, the credit the generator will count"
```

---

### Task 2: docs say which column to sum; plan schema stops claiming 0.5

**Files:**
- Modify: `docs/generation.md` (~line 120–124, the "Indirect volume counts at a discount" bullet)
- Modify: `skills/generation/references/coaching.md` (~line 260–262, "what each candidate is worth")
- Modify: `skills/generation/assets/schema/plan.schema.json` (`targets.description`, ~line 85)

- [ ] **Step 1: docs/generation.md**

Replace the bullet's last sentence

```
every group to earn real direct work. The plan JSON embeds each exercise's raw volume map, so
  any other accounting can be recomputed from the record.
```

with

```
every group to earn real direct work. The brief shows both: `volume` is the raw map the plan
  records, `effective_volume` is what the generator will actually count — sum that column, not
  the raw one. The plan JSON embeds each exercise's raw volume map, so any other accounting can
  be recomputed from the record.
```

- [ ] **Step 2: coaching.md**

In § What the script actually enforces, change

```
session, what the week delivers against each target, what each candidate is worth — and stops
there.
```

to

```
session, what the week delivers against each target, what each candidate is worth
(`effective_volume` in the brief — the only column whose sum matches the check table) — and
stops there.
```

- [ ] **Step 3: plan.schema.json**

In `targets.description`, replace `(each set adds 1.0 for direct muscles, 0.5 for indirect ones)` with `(each set adds the exercise's coefficient for direct muscles, and the coefficient times the config's indirect discount for indirect ones)`. Keep the JSON valid.

- [ ] **Step 4: Validate and run the suite**

Run: `python scripts/validate-skills.py; bash tests/skills/run-skill-tests.sh` → exit 0; Passed 7, Failed 0. (`validate-skills.py` re-validates `plan.example.json` against the edited schema — the description change cannot break it, but this is the check.)

- [ ] **Step 5: Commit**

```bash
git add docs/generation.md skills/generation/references/coaching.md skills/generation/assets/schema/plan.schema.json
git commit -m "Docs: sum effective_volume, not the raw map; plan schema stops claiming 0.5 per indirect set"
```

---

## Self-review

- Spec §1 → T1 step 3; §2 → T1 step 4; §3 → T1 step 1; §4 → T2 step 1; §5 → T2 step 2; §6 → T2 step 3.
- Constraint check: no new arithmetic (`r["effective"]` reused); tests read the discount from config; plan JSON untouched (only a schema description string); rules.md/SKILL.md untouched.
- Names consistent: `effective_volume` everywhere; `config["indirect_discount"]` in both tests.
