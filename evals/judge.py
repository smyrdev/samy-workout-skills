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
    except (OSError, ValueError) as e:
        # ValueError covers UnicodeDecodeError: non-UTF-8 bytes from a CLI
        # response are an invalid-response case, not a crash.
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
