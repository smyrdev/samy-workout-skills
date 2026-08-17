# Eval pipeline: Python logic, one shell leaf

2026-08-17. Supersedes the shell/heredoc layout that `2026-08-12-quality-evals-design.md`
specified for `run-evals.sh` and `judge.sh`. Everything else in that spec — personas,
rubric, outcomes model, results layout, the tuning loop — stands unchanged.

## Why

`run-evals.sh` and `judge.sh` grew five embedded Python heredocs between them. The
result is a hybrid that is hard to read and hard to edit — especially for the repo's
owner, who works comfortably in Python and not in bash. The original sh choice was a
convention (the test suite is bash), not a technical requirement; nothing in the
pipeline needs shell except one thing, covered below.

## The shape

Python is the brain. Shell survives as exactly one tiny leaf.

```
evals/
  run-evals.py          the runner: persona loop, outcome routing, report composition
  judge.py              judging: prompt build, retry ladder, validation, aggregation,
                        verdict writing; importable by run-evals.py, runnable alone
  scripts/call-cli.sh   ~10 lines: timeout -k 10 $TIMEOUT "$CLAUDE_BIN" -p
                        --output-format json < prompt-file > response-file
```

`run-evals.sh` and `judge.sh` are deleted. `run-evals.py` and `judge.py` take exactly
the flags the .sh files took, write exactly the artifacts the .sh files wrote
(`prompt.txt`, `response-jN-aM.json`, `judge-N.json`, `verdict.json`, `report.md`, the
`report: <path>` stdout line), and exit with the same codes under the same conditions.
The outcomes model — scored / generation-failed / indeterminate, findings never fail
the run, exit code reflects infrastructure only — carries over untouched.

`run-evals.py` calls `generate.py` via subprocess (python to python, portable) and
imports `judge.py` as a module rather than shelling out to it.

## Why the one shell leaf stays

`call-cli.sh` exists for two concrete reasons, both verified by the existing tests:

1. **`timeout -k` already enforces the deadline against a CLI that ignores SIGTERM**,
   and the stubborn-CLI test proves it. Reimplementing process-tree kill portably in
   Python (taskkill on Windows, process groups on POSIX) is the riskiest part of a
   full rewrite; the leaf sidesteps it.
2. **It keeps the fake CLIs working.** The test suite's fakes are bash scripts. A pure
   Python judge on Windows could not execute them (no shebang support outside bash);
   invoking the CLI through `bash call-cli.sh` means bash resolves them exactly as it
   does today.

Consequence: judging still requires Git Bash — which the test suite already requires,
so no new dependency. `--skip-judge`, the free tuning loop, never touches shell at all.

## Readability is a requirement, not a style preference

The rewrite exists so the owner can read and modify the pipeline. Concretely:

- Small named functions, one job each — `build_prompt`, `validate_verdict`,
  `judge_once`, `aggregate`, `compose_report` — arranged top-down so each file reads
  like the pipeline it implements.
- Plain stdlib Python: `pathlib`, `json`, `subprocess`, `statistics`, `argparse`.
  No new dependencies, no cleverness.
- Comments explain the non-obvious decisions (why a timeout is not retried, why the
  red-flag cap is re-applied after the median), the same voice as the rest of the repo.
- If a function does not fit on one screen, it is doing too much.

## Tests

`tests/skills/test-eval-harness.sh` stays a bash test file, consistent with the rest of
the suite. Its fakes, markers, and assertions are unchanged; only the entry-point lines
change (`bash "$JUDGE"` → `python "$JUDGE"` with the new paths). The suite already
covers every path offline: valid verdict, garbage + retry, garbage twice, timeout
enforcement, median-of-3, bad red-flag shapes, the smoke run, `--skip-judge`, and the
missing-dataset preflight. Green suite = behavior preserved.

`evals/README.md` command examples switch from `bash evals/run-evals.sh …` to
`python evals/run-evals.py …`.

## Out of scope

- The rest of `tests/skills/` stays bash — repo-wide convention, not this problem.
- No behavior changes, however tempting, ride along. Anything the Mira eval surfaced
  (shoulder-volume crediting, novice exercise difficulty) is separate work.
