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
