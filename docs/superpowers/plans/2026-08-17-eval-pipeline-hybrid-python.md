# Eval Pipeline Hybrid Python Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `evals/run-evals.sh` and `evals/judge.sh` with readable Python (`run-evals.py`, `judge.py`) plus one ~10-line shell leaf (`scripts/call-cli.sh`), preserving every flag, artifact, and exit code.

**Architecture:** Python is the brain: prompt building, retry ladder, validation, aggregation, outcome routing, report composition. The single shell leaf makes the one CLI call under `timeout -k`, which both enforces the deadline against a SIGTERM-ignoring CLI and lets bash resolve the test suite's bash-script fake CLIs. `run-evals.py` imports `judge.py` as a module; the existing offline test suite is the safety net and changes only its entry-point lines.

**Tech Stack:** Python 3 stdlib only (`argparse`, `json`, `pathlib`, `re`, `statistics`, `subprocess`, `datetime`). Git Bash for the leaf. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-17-eval-pipeline-hybrid-python-design.md`

## Global Constraints

- **Behavior is frozen.** Same CLI flags, same artifacts (`prompt.txt`, `response-jN-aM.json`, `judge-N.json`, `verdict.json`, `invalid-reason.txt`, `gen-error.txt`, `report.md`, the `report: <path>` stdout line, the `<persona>: <status>` lines), same exit codes (0 all-verdicts, 1 indeterminate, 2 preflight/usage) under the same conditions. The green test suite is the proof; no behavior tweak rides along.
- **Readability is a requirement:** small named functions arranged top-down, one job each, none longer than a screen; comments explain non-obvious decisions in the repo's existing voice.
- Every file open — read or write — passes `encoding="utf-8"`.
- Any path handed to bash as an argument is converted to forward slashes first (Git Bash mangles backslashes inside quoting).
- The test file `tests/skills/test-eval-harness.sh` keeps its fakes, markers, and assertions byte-identical; only entry-point invocations and the header comment change.
- Verification commands run from the repo root (the worktree root).

---

### Task 1: `judge.py` + the shell leaf

**Files:**
- Create: `evals/scripts/call-cli.sh`
- Create: `evals/judge.py`
- Modify: `tests/skills/test-eval-harness.sh` (lines 1–11 header, line 19, lines 114–119 `judge()` helper)
- Test: `tests/skills/test-eval-harness.sh` (existing assertions, judge sections)

**Interfaces:**
- Consumes: nothing from other tasks. `CLAUDE_BIN` env var (default `claude`), honored inside the leaf.
- Produces: `judge.judge(rubric: Path, persona: Path, plan: Path, outdir: Path, timeout: int = 120, judges: int = 1) -> int` (0 scored, 1 indeterminate) and `judge.CRITERIA: list[str]` — Task 2 imports both. CLI: `python evals/judge.py <rubric> <persona> <plan> <outdir> [--timeout N] [--judges N]`, exit 2 on usage/missing input.

- [ ] **Step 1: Write the shell leaf**

Create `evals/scripts/call-cli.sh`:

```bash
#!/usr/bin/env bash
# call-cli.sh — the eval pipeline's one shell leaf.
#
#   call-cli.sh <timeout-seconds> <prompt-file> <response-file>
#
# Why this is shell (see the 2026-08-17 design spec): `timeout -k` makes the
# deadline real against a CLI that ignores SIGTERM, and bash resolves a
# CLAUDE_BIN that is a shebang script — which is exactly what the offline
# test fakes are. Everything else about judging lives in judge.py.
set -uo pipefail
CLI="${CLAUDE_BIN:-claude}"
exec timeout -k 10 "$1" "$CLI" -p --output-format json < "$2" > "$3" 2>&1
```

- [ ] **Step 2: Repoint the test's judge entry (this is the failing test)**

In `tests/skills/test-eval-harness.sh`:

Line 19, change:
```bash
JUDGE="$REPO_ROOT/evals/judge.sh"
```
to:
```bash
JUDGE="$REPO_ROOT/evals/judge.py"
```

In the `judge()` helper (around line 114), change `bash "$JUDGE"` to `python "$JUDGE"`:
```bash
judge() {  # judge <fake> <out-dir> [extra flags...]
    local fake="$1" out="$2"; shift 2
    CLAUDE_BIN="$PROJECT/$fake" python "$JUDGE" \
        "$PROJECT/rubric.md" "$PROJECT/persona.yaml" "$PROJECT/plan.md" \
        "$out" "$@"
}
```

In the header comment (line 2), change `evals/judge.sh` to `evals/judge.py`.

- [ ] **Step 3: Run the test to verify it fails**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: the judge sections FAIL (`python .../judge.py` — no such file); the `run-evals.sh` sections still pass (the old `judge.sh` still exists and the runner still calls it).

- [ ] **Step 4: Write `evals/judge.py`**

```python
#!/usr/bin/env python
"""judge.py — rubric + persona.yaml + plan.md -> claude -p -> verdict.json

One judging is one CLI call, made through scripts/call-cli.sh — the
pipeline's single shell leaf; see that file for why it exists. The prompt
goes to the CLI on stdin from a file, never as an argument: rubric + plan
together can blow past Windows' ~32KB argv limit. The CLI answers with an
envelope — a JSON object whose "result" field holds the judge's text — and
the verdict JSON is parsed out of that.

Failure ladder per judging: bad output -> one retry -> give up. A timeout
is not retried (it would just time out again). Either way a verdict.json is
still written — {"outcome": "indeterminate", ...} — and the exit code is 1,
so a caller can never mistake infra noise for a quality signal.

The prompt and every raw CLI response are saved next to the verdict: when a
run goes indeterminate, the postmortem is already on disk.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
CALL_CLI = EVALS_DIR / "scripts" / "call-cli.sh"

CRITERIA = ["selection_suitability", "balance_and_coverage",
            "ordering_and_structure", "persona_fit", "red_flags"]

VERDICT_SHAPE = """{
  "criteria": [
    {"name": "selection_suitability", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "balance_and_coverage", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "ordering_and_structure", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "persona_fit", "evidence": "...", "reasoning": "...", "score": 4},
    {"name": "red_flags", "evidence": "...", "reasoning": "...", "score": 5}
  ],
  "red_flags": [],
  "overall": 4.2,
  "summary": "one paragraph for the report table"
}"""


def build_prompt(rubric, persona, plan):
    """Fixed instructions + the exact verdict shape + rubric + persona + plan.

    Asks for evidence and reasoning BEFORE each score, the exact criterion
    names in the exact order, and makes the judge compute overall and apply
    the red-flag cap itself — this program validates, never recomputes.
    """
    return "\n".join([
        "You are an impartial judge scoring one generated training plan for one",
        "persona, using the rubric below. Use no tools. Respond with pure JSON",
        "only — no prose before or after it, no markdown fences.",
        "",
        "The JSON must have exactly this shape:",
        VERDICT_SHAPE,
        "",
        "Rules:",
        "- Score the five criteria in exactly this order, with exactly these",
        "  names: selection_suitability, balance_and_coverage,",
        "  ordering_and_structure, persona_fit, red_flags.",
        "- For each criterion, write the evidence (citing specific exercises and",
        "  days from the plan) and your reasoning BEFORE choosing the score.",
        "  Scores are integers from 1 to 5.",
        "- red_flags is a list of short strings, one per red flag; empty if none.",
        "- Compute overall yourself. If red_flags is non-empty, overall must not",
        "  exceed 2.",
        "- summary is one paragraph a report table can quote.",
        "",
        "=== RUBRIC ===",
        rubric.read_text(encoding="utf-8"),
        "=== PERSONA ===",
        persona.read_text(encoding="utf-8"),
        "=== PLAN ===",
        plan.read_text(encoding="utf-8"),
    ])


def _bash_path(p):
    # Git Bash takes C:/-style paths; backslashes do not survive its quoting.
    return str(p).replace("\\", "/")


def call_cli(prompt_file, response_file, timeout):
    """One CLI call through the shell leaf. Returns the exit code; 124 and
    137 mean the deadline fired (timeout's TERM and KILL exits)."""
    return subprocess.run(
        ["bash", _bash_path(CALL_CLI), str(timeout),
         _bash_path(prompt_file), _bash_path(response_file)]).returncode


def validate(response_file):
    """Parse a raw CLI response into a verdict.

    Returns (verdict, None) when valid, (None, reason) otherwise. Tolerates
    the model wrapping its JSON in ``` fences.
    """
    try:
        raw = response_file.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"cannot read response: {e}"

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return None, "CLI output is not a JSON envelope"
    if not isinstance(envelope, dict) or not isinstance(envelope.get("result"), str):
        return None, "envelope has no string 'result' field"

    text = envelope["result"].strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        v = json.loads(text)
    except json.JSONDecodeError:
        return None, "the judge's text is not JSON"

    crits = v.get("criteria")
    if not isinstance(crits, list) or len(crits) != len(CRITERIA):
        return None, f"expected {len(CRITERIA)} criteria"
    for crit, expected in zip(crits, CRITERIA):
        if not isinstance(crit, dict) or crit.get("name") != expected:
            return None, f"criterion out of place: expected '{expected}'"
        score = crit.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            return None, f"{expected}: score must be an integer 1-5"
        for key in ("evidence", "reasoning"):
            if not isinstance(crit.get(key), str) or not crit[key].strip():
                return None, f"{expected}: empty {key}"

    if not isinstance(v.get("red_flags"), list):
        return None, "red_flags must be a list"
    if not all(isinstance(f, str) for f in v["red_flags"]):
        return None, "red_flags must be a list of strings"
    overall = v.get("overall")
    if not isinstance(overall, (int, float)) or isinstance(overall, bool):
        return None, "overall must be a number"
    if not 1 <= overall <= 5:
        return None, "overall must be between 1 and 5"
    if v["red_flags"] and overall > 2:
        return None, "red flags present but the cap on overall was not applied"
    if not isinstance(v.get("summary"), str) or not v["summary"].strip():
        return None, "empty summary"

    return v, None


def aggregate(verdicts):
    """One judging passes through as-is; several take the per-criterion
    median, the median overall, and the union of red flags — with the cap
    re-applied to the median, since a red flag any judge saw must still cap
    the aggregate."""
    if len(verdicts) == 1:
        return {"outcome": "scored", **verdicts[0]}
    criteria = [{"name": name,
                 "score": statistics.median(v["criteria"][i]["score"]
                                            for v in verdicts)}
                for i, name in enumerate(CRITERIA)]
    red_flags = sorted({flag for v in verdicts for flag in v["red_flags"]})
    overall = statistics.median(v["overall"] for v in verdicts)
    if red_flags and overall > 2:
        overall = 2
    return {"outcome": "scored", "judges": len(verdicts), "criteria": criteria,
            "red_flags": red_flags, "overall": overall,
            "summary": verdicts[0]["summary"],
            "summaries": [v["summary"] for v in verdicts]}


def write_indeterminate(outdir, reason):
    (outdir / "verdict.json").write_text(
        json.dumps({"outcome": "indeterminate", "reason": reason}, indent=2),
        encoding="utf-8")


def judge(rubric, persona, plan, outdir, timeout=120, judges=1):
    """Judge one plan; returns 0 (verdict.json is scored) or 1 (indeterminate)."""
    outdir.mkdir(parents=True, exist_ok=True)
    prompt_file = outdir / "prompt.txt"
    prompt_file.write_text(build_prompt(rubric, persona, plan), encoding="utf-8")

    verdicts = []
    for j in range(1, judges + 1):
        verdict = reason = None
        for attempt in (1, 2):
            raw = outdir / f"response-j{j}-a{attempt}.json"
            rc = call_cli(prompt_file, raw, timeout)
            if rc in (124, 137):
                write_indeterminate(outdir, f"judging {j} timed out after {timeout}s")
                return 1
            verdict, reason = validate(raw)
            if verdict is not None:
                (outdir / f"judge-{j}.json").write_text(
                    json.dumps(verdict) + "\n", encoding="utf-8")
                break
            (outdir / "invalid-reason.txt").write_text(
                reason + "\n", encoding="utf-8")
        if verdict is None:
            write_indeterminate(
                outdir,
                f"judging {j} produced an invalid verdict twice: {reason or 'unknown'}")
            return 1
        verdicts.append(verdict)

    try:
        final = aggregate(verdicts)
    except Exception:
        write_indeterminate(outdir, "final verdict aggregation failed")
        return 1
    (outdir / "verdict.json").write_text(
        json.dumps(final, indent=2), encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        usage="judge.py <rubric.md> <persona.yaml> <plan.md> <out-dir> "
              "[--timeout N] [--judges N]")
    parser.add_argument("rubric", type=Path)
    parser.add_argument("persona", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--judges", type=int, default=1)
    args = parser.parse_args(argv)

    for f in (args.rubric, args.persona, args.plan):
        if not f.is_file():
            print(f"judge.py: missing input: {f}", file=sys.stderr)
            return 2
    return judge(args.rubric, args.persona, args.plan, args.outdir,
                 args.timeout, args.judges)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the test to verify the judge sections pass**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: PASS end to end — judge sections against `judge.py`, runner sections still against the untouched `run-evals.sh`. Pay attention to the two behavior-sensitive checks: "the CLI was called exactly twice" (retry ladder) and "a CLI that ignores SIGTERM is killed near the deadline" (the leaf's `timeout -k`).

- [ ] **Step 6: Commit**

```bash
git add evals/scripts/call-cli.sh evals/judge.py tests/skills/test-eval-harness.sh
git commit -m "Rewrite judge.sh as judge.py with a single call-cli.sh shell leaf

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: `run-evals.py`

**Files:**
- Create: `evals/run-evals.py`
- Modify: `tests/skills/test-eval-harness.sh` (line 20, and the four `bash "$RUNNER"` invocations around lines 251, 272, 287, 299)
- Test: `tests/skills/test-eval-harness.sh` (existing assertions, runner sections)

**Interfaces:**
- Consumes: `judge.judge(rubric, persona, plan, outdir, timeout=, judges=) -> int` and `judge.CRITERIA` from Task 1 (plain `import judge` — both files sit in `evals/`, and `sys.path[0]` is the script's directory).
- Produces: CLI `python evals/run-evals.py [--persona NAME] [--skip-judge] [--judges N] [--timeout N] [--dataset-dir DIR] [--results-dir DIR]`. Nothing imports it.

- [ ] **Step 1: Repoint the test's runner entry (this is the failing test)**

In `tests/skills/test-eval-harness.sh`:

Line 20, change:
```bash
RUNNER="$REPO_ROOT/evals/run-evals.sh"
```
to:
```bash
RUNNER="$REPO_ROOT/evals/run-evals.py"
```

Change every `bash "$RUNNER"` to `python "$RUNNER"` — four call sites: the smoke run, the `--skip-judge` run, the indeterminate run, and the missing-dataset preflight. Example (smoke run):
```bash
CLAUDE_BIN="$PROJECT/ok" python "$RUNNER" --persona mira \
    --dataset-dir "$FIXDS" --results-dir "$PROJECT/results" > /dev/null 2>&1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: judge sections PASS, runner sections FAIL (no `run-evals.py`).

- [ ] **Step 3: Write `evals/run-evals.py`**

```python
#!/usr/bin/env python
"""run-evals.py — the eval pipeline: generate a plan per persona, judge each
against the rubric, compose one comparison report.

    python evals/run-evals.py                     all personas
    python evals/run-evals.py --persona mira      one persona
    python evals/run-evals.py --skip-judge        generate only, no CLI needed
    python evals/run-evals.py --judges 3          median-of-3 judging

--dataset-dir and --results-dir exist so the smoke test can point everything
at temp dirs; the defaults are the documented layout.

The exit code reflects infrastructure only: preflight failure or any
indeterminate judging is non-zero. A generation refusal is a FINDING — its
stderr lands in the report — and findings never fail the run.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import judge

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
GENERATE = REPO_ROOT / "skills" / "generation" / "scripts" / "generate.py"
CLONE_CMD = ("git clone --depth 1 "
             "https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset")


def cli_answers_version():
    """Probe the judge CLI through bash, exactly the way judging will call it
    — so a CLAUDE_BIN that is a shebang script counts as present."""
    probe = subprocess.run(["bash", "-c", '"${CLAUDE_BIN:-claude}" --version'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return probe.returncode == 0


def fresh_run_dir(results_dir):
    """A new results folder per run, never overwritten."""
    base = results_dir / datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir, n = base, 1
    while run_dir.exists():
        n += 1
        run_dir = Path(f"{base}-{n}")
    run_dir.mkdir(parents=True)
    return run_dir


def generate_plan(src, pdir, dataset_dir, run_date):
    """Run the real generator for one persona. On refusal, leave its stderr
    in gen-error.txt — a finding for the report, not an error."""
    cmd = [sys.executable, str(GENERATE),
           "--profile", str(src / "profile.json"),
           "--program", str(src / "program.json")]
    if (src / "rules.json").is_file():
        cmd += ["--rules", str(src / "rules.json")]
    cmd += ["--dataset-dir", str(dataset_dir), "--today", run_date,
            "--write", str(pdir / "plan.json"),
            "--write-md", str(pdir / "plan.md")]

    gen_error = pdir / "gen-error.txt"
    with open(gen_error, "w", encoding="utf-8") as err:
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err).returncode
    if rc == 0:
        gen_error.unlink()
        return True
    return False


def compose_report(run_dir):
    """Compose report.md from what is on disk. Outcomes are deliberately read
    back from files rather than threaded through in memory: gen-error.txt
    present = generation-failed, verdict.json's outcome field says scored or
    indeterminate, a plan with neither = generated but not judged. A human
    can re-derive the same table."""
    rows, summaries, failures, indets = [], [], [], []
    for pdir in sorted(d for d in run_dir.iterdir() if d.is_dir()):
        p = pdir.name
        gen_error = pdir / "gen-error.txt"
        verdict_file = pdir / "verdict.json"
        if gen_error.exists():
            rows.append((p, "generation-failed", None))
            failures.append((p, gen_error.read_text(encoding="utf-8").strip()))
        elif verdict_file.exists():
            v = json.loads(verdict_file.read_text(encoding="utf-8"))
            if v.get("outcome") == "scored":
                scores = {c["name"]: c["score"] for c in v["criteria"]}
                rows.append((p, "scored",
                             (scores, v["overall"], len(v["red_flags"]))))
                summaries.append((p, v["summary"]))
            else:
                rows.append((p, "indeterminate", None))
                indets.append((p, v.get("reason", "no reason recorded")))
        else:
            rows.append((p, "generated", None))

    lines = [f"# Eval report — {run_dir.name}", ""]
    lines.append("| persona | " + " | ".join(judge.CRITERIA) + " | overall | red flags |")
    lines.append("|" + "---|" * (len(judge.CRITERIA) + 3))
    for p, status, data in rows:
        if status == "scored":
            scores, overall, red = data
            cells = [str(scores.get(n, "?")) for n in judge.CRITERIA]
            lines.append(f"| {p} | " + " | ".join(cells) + f" | {overall} | {red} |")
        else:
            cells = ["—"] * len(judge.CRITERIA)
            lines.append(f"| {p} | " + " | ".join(cells) + f" | {status} | — |")

    if summaries:
        lines += ["", "## Judge summaries", ""]
        for p, s in summaries:
            lines += [f"**{p}** — {s}", ""]

    if indets:
        lines += ["", "## Indeterminate", ""]
        for p, reason in indets:
            lines += [f"- {p}: {reason}"]

    if failures:
        lines += ["", "## Generation failures", ""]
        for p, err in failures:
            lines += [f"**{p}**", "", "```", err, "```", ""]

    scored = [data for _, status, data in rows if status == "scored"]
    if scored:
        means = {n: sum(s[n] for s, _, _ in scored) / len(scored)
                 for n in judge.CRITERIA}
        weakest = min(means, key=means.get)
        lines += ["", f"Weakest criterion across the matrix: "
                      f"{weakest} (mean {means[weakest]:.1f})"]

    report = run_dir / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {report}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        usage="run-evals.py [--persona NAME] [--skip-judge] [--judges N] "
              "[--timeout N] [--dataset-dir DIR] [--results-dir DIR]")
    parser.add_argument("--persona")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--judges", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dataset-dir", type=Path,
                        default=REPO_ROOT / "datasets" / "exercises-dataset")
    parser.add_argument("--results-dir", type=Path,
                        default=EVALS_DIR / "results")
    args = parser.parse_args(argv)

    # --- preflights -------------------------------------------------------
    if not args.dataset_dir.is_dir():
        print(f"run-evals.py: no dataset at {args.dataset_dir}", file=sys.stderr)
        print("clone it first:", file=sys.stderr)
        print(f"  {CLONE_CMD}", file=sys.stderr)
        return 2
    if not args.skip_judge and not cli_answers_version():
        cli = os.environ.get("CLAUDE_BIN", "claude")
        print(f"run-evals.py: the judge CLI ('{cli}') did not answer --version.",
              file=sys.stderr)
        print("The judge runs through the Claude Code CLI — see evals/README.md.",
              file=sys.stderr)
        return 2

    # --- personas ---------------------------------------------------------
    personas_dir = EVALS_DIR / "personas"
    if args.persona:
        if not (personas_dir / args.persona).is_dir():
            print(f"run-evals.py: no persona named '{args.persona}' "
                  f"under evals/personas/", file=sys.stderr)
            return 2
        personas = [args.persona]
    else:
        personas = sorted(d.name for d in personas_dir.iterdir() if d.is_dir())

    run_date = datetime.date.today().isoformat()
    run_dir = fresh_run_dir(args.results_dir)

    # --- generate, then judge --------------------------------------------
    indeterminate = 0
    for p in personas:
        src = personas_dir / p
        pdir = run_dir / p
        pdir.mkdir(parents=True)

        if not generate_plan(src, pdir, args.dataset_dir, run_date):
            print(f"{p}: generation-failed (stderr saved)")
            continue
        if args.skip_judge:
            print(f"{p}: generated")
            continue

        rc = judge.judge(EVALS_DIR / "rubric" / "plan-quality.md",
                         src / "persona.yaml", pdir / "plan.md", pdir,
                         timeout=args.timeout, judges=args.judges)
        if rc == 0:
            print(f"{p}: scored")
        else:
            print(f"{p}: indeterminate")
            indeterminate = 1

    try:
        compose_report(run_dir)
    except Exception:
        print("run-evals.py: report composition failed", file=sys.stderr)
        return 2
    return indeterminate


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify everything passes**

Run: `bash tests/skills/test-eval-harness.sh`
Expected: PASS end to end — including the smoke run's artifact checks (`plan.json`, `plan.md`, `verdict.json`, `report.md`), the `--skip-judge`-needs-no-CLI check, the indeterminate exit-1 check, and the missing-dataset preflight (exit 2, message contains `git clone`).

- [ ] **Step 5: Commit**

```bash
git add evals/run-evals.py tests/skills/test-eval-harness.sh
git commit -m "Rewrite run-evals.sh as run-evals.py importing judge.py

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Delete the .sh files, update the README

**Files:**
- Delete: `evals/judge.sh`, `evals/run-evals.sh`
- Modify: `evals/README.md` (the Running section's four command lines)
- Test: `bash tests/skills/run-skill-tests.sh` and `python scripts/validate-skills.py`

**Interfaces:**
- Consumes: Task 1's `judge.py` and Task 2's `run-evals.py` fully replacing the .sh files.
- Produces: nothing — cleanup.

- [ ] **Step 1: Delete the shell originals**

```bash
git rm evals/judge.sh evals/run-evals.sh
```

- [ ] **Step 2: Update `evals/README.md`**

In the Running section, change:
```bash
bash evals/run-evals.sh                     # all personas: generate + judge + report
bash evals/run-evals.sh --persona <name>    # one persona
bash evals/run-evals.sh --skip-judge        # generate only — free; for diffing plans
bash evals/run-evals.sh --judges 3          # median-of-3 judging
```
to:
```bash
python evals/run-evals.py                     # all personas: generate + judge + report
python evals/run-evals.py --persona <name>    # one persona
python evals/run-evals.py --skip-judge        # generate only — free; for diffing plans
python evals/run-evals.py --judges 3          # median-of-3 judging
```
In the Requirements section, change the `bash` bullet from `* bash` to
`* bash — only for judging, which calls the CLI through a small shell shim`
(the `--skip-judge` loop is pure Python).

- [ ] **Step 3: Check for stale references**

Run: `grep -rn --include="*.md" --include="*.sh" --include="*.py" -e "run-evals\.sh" -e "judge\.sh" . --exclude-dir=.git --exclude-dir=docs`
Expected: no hits outside `docs/` (historical specs and plans under `docs/superpowers/` stay as written — they describe the past). Fix any hit in living files (README, tests, skills, scripts) to the `.py` names.

- [ ] **Step 4: Run the full verification**

Run: `bash tests/skills/run-skill-tests.sh`
Expected: the whole suite PASSES, including `test-eval-harness.sh`.

Run: `python scripts/validate-skills.py`
Expected: exit 0, clean.

- [ ] **Step 5: End-to-end sanity run (real generator, no tokens)**

Run: `python evals/run-evals.py --persona mira --skip-judge`
Expected: `mira: generated` and a `report: .../report.md` line; the new run folder under `evals/results/` holds `mira/plan.json`, `mira/plan.md`, and `report.md` with a `| mira | — | ... | generated | — |` row.

- [ ] **Step 6: Commit**

```bash
git add evals/README.md
git commit -m "Remove eval .sh pipeline, point README at the Python entry points

Co-Authored-By: Claude <noreply@anthropic.com>"
```
