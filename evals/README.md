# Samy workout skills evals

## Goal

This folder evaluates the quality of what the skills produce. It generates plans for a
fixed matrix of sample personas, has an LLM judge score each plan against a written rubric
(`rubric/plan-quality.md`), and composes a comparison report — so a config tweak can be
evaluated across the whole matrix in one command.

## Requirements

* python
* bash
* the Claude Code CLI, logged in — the judge runs through `claude -p`; nothing else in
  the pipeline needs it, and `--skip-judge` runs without it
* the exercise dataset, cloned locally:

  ```bash
  git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset
  ```

## Running

```bash
bash evals/run-evals.sh                     # all personas: generate + judge + report
bash evals/run-evals.sh --persona <name>    # one persona
bash evals/run-evals.sh --skip-judge        # generate only — free; for diffing plans
bash evals/run-evals.sh --judges 3          # median-of-3 judging
```

Each run writes a fresh folder `evals/results/<YYYY-MM-DD-HHMM>/` (gitignored, never
overwritten) holding per-persona `plan.json`, `plan.md`, `verdict.json`, and a `report.md`.

## Outcomes

Each persona ends a run in one of three states:

* `scored` — the generator ran and the judge returned a valid verdict.
* `generation-failed` — `generate.py` refused. This is a finding, not an error: the
  report shows the generator's stderr verbatim, and the message names the file to fix.
* `indeterminate` — the judge timed out or emitted garbage twice. Infra noise; reported,
  never scored.

The runner's exit code reflects infrastructure only: 0 means every persona reached a
verdict, non-zero means something failed to run. Scores never gate.

## Tuning loop

The intended workflow when retuning `volume.config.json`, `generate.config.json`, or
`datasets.json`:

1. Tweak the config.
2. `bash evals/run-evals.sh --skip-judge` — free, no CLI needed.
3. Diff the new run's plans against the last run's (within a run, `--today` is pinned,
   so plan diffs are pure signal).
4. Judge only when the diff looks interesting.

Scores are comparable within a run (persona vs persona, before vs after a tweak in the
same sitting), not across long time spans — the CLI's underlying model can drift.
