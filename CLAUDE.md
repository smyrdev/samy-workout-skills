# Working in this repository

Two portable [Agent Skills](https://agentskills.io/specification) — `skills/onboarding/` builds a
training profile, `skills/generation/` turns it into a plan. `README.md` has the file map and the
user-facing walkthrough; `docs/` has the rationale (`schema.md`, `generation.md`) and the
hand-editing guides (`*-fields.md`).

## Commands

```
python scripts/validate-skills.py                        # validate everything, exit 0 clean
bash tests/skills/run-skill-tests.sh                     # offline test suite (-i adds agent tests)
python skills/onboarding/scripts/volume.py --self-test    # volume model self-test
python skills/generation/scripts/generate.py --self-test  # generator self-test, offline
python skills/generation/scripts/generate.py --brief ...   # the candidates; then --selection to write
git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset
```

Run the validator and the offline suite before committing. Both must be clean.

## Data layout

`profile/` is the person's data and is gitignored except `.gitkeep`. Write ownership is split
three ways and never crossed: onboarding writes `profile.json` (once) and
`programs/program-YYYY-MM-DD.json` (one per training block, including the volume block
`volume.py` computes); generation writes `plans/` only (one dated `.json` + `.md` pair per run);
`rules.md` is written by the person alone — hand-written Markdown, parsed by `generate.py`;
generation reads it and offers snippets, never edits it. Never commit a real profile or suggest force-adding one.

One repository holds one profile. There is no slug, no per-person directory, no "which person is
this?" step — `user.name` is a display label, not a path. Do not reintroduce one.

## Rules

- One owner per number: `volume.py` computes the per-muscle weekly set allocation, `generate.py`
  consumes it. Generation never recomputes or adjusts targets, and refuses a program file whose
  volume block is missing or incomplete rather than estimating one.
- One owner per decision: `generate.py` decides what is *legal* and what each muscle is *owed*;
  the model decides which exercise, in what order, paired how, at what effort. The script refuses
  exactly two things — an exercise it never offered, and a rep target under the floor in
  `generate.config.json`. Everything else in `skills/generation/references/coaching.md` is
  guidance, on purpose. Do not add a cap to the script because a rule in `coaching.md` sounds like
  one.
- `skills/*/SKILL.md` is portable: no vendor tool names, no absolute or Windows paths, paths are
  skill-root-relative and each pointer says *when* to read the file. `.claude/skills/*/SKILL.md`
  are pointers, not forks — a change to a flow goes in the portable file, never into a wrapper.
- Every tunable number lives in `scripts/*.config.json`, never in a script, a SKILL.md, or here.
- Everything dataset-specific — field names, equipment tiers, muscle vocabulary — lives in
  `skills/generation/assets/datasets.json`, none of it in `generate.py`. Do not "fix" a dataset
  quirk in the script; extend the descriptor. A new dataset is a new descriptor entry, not code.
- `generate.py` refuses unknown values — an unmapped muscle, an untiered equipment name — rather
  than guessing. Keep it that way; the fix is always a descriptor edit.
- `skills/*/evals/files/` holds copies of the shipped examples, never a real profile. Eval run
  outputs go to `<skill>-workspace/`, gitignored. Assertions are revised after runs, not before.
