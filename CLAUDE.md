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
.claude/skills/onboard/SKILL.md  Claude Code pointer + environment bindings, not a fork
scripts/validate-skills.py     validates the whole skill against its own schemas
docs/schema.md                 rationale: why the schema looks the way it does
docs/onboarding.md             original hand-written spec — left untouched, see below
profiles/                      user data — gitignored, written only by the onboarding skill
```

`profiles/<slug>/profile.json` is written once. `profiles/<slug>/programs/program-YYYY-MM-DD.json`
holds one file per training block — the onboarding skill's answers. `profiles/<slug>/plans/` is
where a future generation skill writes what it produces; the two directories never blur.

## Commands

```
python scripts/validate-skills.py                                    # validate everything, exit 0 clean
python skills/onboarding/scripts/volume.py --self-test                # volume model self-test
cp skills/onboarding/examples/profile.example.json profiles/<slug>/profile.json   # hand-fill path
```

## Rules

- `profiles/` is user data. It is gitignored in full except `.gitkeep` — never commit a real
  profile, never suggest force-adding one.
- Only the onboarding skill writes under `profiles/`. A future generation skill reads
  `profile.json` and the latest `programs/*.json` and writes only under `plans/`.
- `skills/onboarding/SKILL.md` is portable: no vendor tool names, no absolute or Windows paths,
  frontmatter carries only `name` and `description`. `.claude/skills/onboard/SKILL.md` is a
  pointer to it, not a fork — a change to the flow goes in the portable file, never copied into
  the wrapper.

`docs/schema.md` has the "why" behind the schema. `docs/onboarding.md` is the original
hand-written spec, kept byte-identical to the copy in the sibling `samy-workouts` repository —
left alone on purpose, typos included.
