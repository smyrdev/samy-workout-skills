# Working in this repository

## Where things are

```
skills/onboarding/
  SKILL.md                    the flow, as pointers. Rarely edited.
  questions.yaml               the interview — edit to change what is asked
  rules.md                     profile resolution, validation, updating, echo-before-write
  FIELDS.md                    "what do I type here", for hand-editing a profile
  schema/profile.schema.json   machine contract for profile.json
  schema/program.schema.json   machine contract for programs/program-*.json
  examples/profile.example.json  copy-to-start sample
  examples/program.example.json  copy-to-start sample
  scripts/volume.py            the volume algorithm — ~120 lines, no numbers
  scripts/volume.config.json   every number the volume model uses — edit to retune it
skills/generation/
  SKILL.md                    the flow, as pointers. Rarely edited.
  rules.md                     dataset cache, personal rules, echo-before-write, never-dos
  FIELDS.md                    hand-editing guide for rules.json and plan files
  datasets.json                dataset registry — ALL dataset-specific knowledge lives here
  schema/plan.schema.json      machine contract for plans/plan-*.json
  schema/rules.schema.json     machine contract for profiles/<slug>/rules.json
  examples/                    copy-to-start samples (plan is genuine generator output)
  scripts/generate.py          the fitting algorithm — no numbers, no dataset field names
  scripts/generate.config.json every dataset-independent number and default rule
  scripts/generate.fixture.json  small offline dataset for the self-test
.claude/skills/onboard/SKILL.md   Claude Code pointer + environment bindings, not a fork
.claude/skills/generate/SKILL.md  same, for the generation skill
scripts/validate-skills.py     validates both skills against their own schemas
tests/skills/                  bash suite — script CLIs, prose policy, agent behaviour
docs/schema.md                 rationale: why the profile/program schema looks the way it does
docs/generation.md             rationale: descriptor format, fitting model, cache design
docs/onboarding.md             original hand-written spec — left untouched, see below
profiles/                      user data — gitignored
datasets/                      cloned exercise datasets — a gitignored local cache
```

`profiles/<slug>/profile.json` is written once. `profiles/<slug>/programs/program-YYYY-MM-DD.json`
holds one file per training block — the onboarding skill's answers, including the volume block
`volume.py` computes. `profiles/<slug>/plans/` holds what the generation skill produces, one dated
pair (`.json` + `.md`) per run. `profiles/<slug>/rules.json` is the person's hand-written
generation preferences. The directories never blur.

## Commands

```
python scripts/validate-skills.py                                    # validate everything, exit 0 clean
bash tests/skills/run-skill-tests.sh                                 # offline test suite (-i adds agent tests)
python skills/onboarding/scripts/volume.py --self-test                # volume model self-test
python skills/generation/scripts/generate.py --self-test              # generator self-test, offline
git clone --depth 1 https://github.com/smyrdev/exercises-dataset datasets/exercises-dataset
cp skills/onboarding/examples/profile.example.json profiles/<slug>/profile.json   # hand-fill path
```

## Rules

- `profiles/` is user data. It is gitignored in full except `.gitkeep` — never commit a real
  profile, never suggest force-adding one.
- Write ownership under `profiles/<slug>/` is split three ways and never crossed: onboarding
  writes `profile.json` and `programs/`; generation writes `plans/` only; `rules.json` is written
  by the person alone — generation reads it and offers snippets, never edits it.
- One owner per number: `volume.py` computes the per-muscle weekly set allocation, `generate.py`
  consumes it. Generation never recomputes or adjusts targets, and refuses a program file whose
  volume block is missing or incomplete rather than estimating one.
- Both `skills/*/SKILL.md` files are portable: no vendor tool names, no absolute or Windows
  paths, frontmatter carries only `name` and `description`. The `.claude/skills/*/SKILL.md`
  wrappers are pointers, not forks — a change to a flow goes in the portable file, never copied
  into a wrapper.
- `datasets/` is a cache of cloned exercise datasets, never committed. Everything
  dataset-specific — field names, equipment tiers, muscle vocabulary mapping — lives in
  `skills/generation/datasets.json`, and none of it in `generate.py`. Do not "fix" a dataset
  quirk by hardcoding it in the script; extend the descriptor. Supporting a new dataset is a new
  descriptor entry, not a code change.
- `generate.py` refuses unknown values — an unmapped muscle, an untiered equipment name — rather
  than guessing. Keep it that way; the fix is always a descriptor edit.

`docs/schema.md` has the "why" behind the profile and program schema; `docs/generation.md` the
same for the generation side. `docs/onboarding.md` is the original hand-written spec, kept
byte-identical to the copy in the sibling `samy-workouts` repository — left alone on purpose,
typos included.
