# Skill tests

Tests for the skills in this repository. Offline by default — no network, no API key, no agent.
The tests that drive a real agent are opt-in behind `--integration`.

## Division of labour

`scripts/validate-skills.py` owns the **static contracts**: frontmatter shape and the Agent
Skills spec constraints (name/description/compatibility limits, name equals directory, body under
500 lines, wrapper descriptions mirroring their portable twins), SKILL.md vendor-neutrality, every
`stores:` path in `references/questions.yaml` resolving against the schemas, the shipped examples
validating, `volume.config.json` covering every schema enum, `assets/datasets.json` and
`generate.config.json` covering every value the generator can meet, both script `--self-test`s,
and the shape of each skill's `evals/evals.json` and `evals/trigger_queries.json`. Do not re-implement those checks here; two owners for one check means one of them
goes stale. `test-validate-skills.sh` wires the validator into this suite rather than repeating it.

This suite owns what that validator cannot see: the **command-line behaviour** of the scripts
(exit codes, file merging, determinism), the **prose policy** the skills promise, and **agent
behaviour** when a skill is actually loaded.

## Requirements

- bash with GNU coreutils — `timeout -k` and `mktemp` are load-bearing. Git Bash on Windows
  qualifies; stock macOS ships no `timeout`
- Python 3 on PATH as `python`
- Claude Code CLI installed and in PATH (`claude --version` should work) — **only** for `--integration`

## Running tests

From the repository root:

```bash
bash tests/skills/run-skill-tests.sh                                  # offline suite
bash tests/skills/run-skill-tests.sh --verbose                        # stream each assertion
bash tests/skills/run-skill-tests.sh --test test-generation-script.sh # one file
bash tests/skills/run-skill-tests.sh --integration                    # add the agent tests (slow, costs tokens)
bash tests/skills/run-skill-tests.sh --timeout 300                    # override the per-file budget
```

Exit code 0 = pass, non-zero = failure. Default budget is 120s per file, 900s with
`--integration`.

## Test files

### test-validate-skills.sh
Runs `scripts/validate-skills.py` so this suite is the single command that checks everything. The
validator is wired in, not re-implemented — it stays the sole owner of the static contracts above.
It runs with `--skills-only`, which skips the gitignored real profile under `profile/`: user
data no other machine has must never fail a suite that runs clean everywhere else. Run the
validator bare to check the real profile too.

### test-runner.sh
`run-skill-tests.sh`'s own gates: an unknown `--test` name is an error rather than a skip, a
listed test file that has gone missing fails the run rather than decorating a green one, and
`--test` cannot smuggle an integration test past the `--integration` gate.

### test-agent-harness.sh
`run_claude` itself, the harness the two agent tests are built on. Offline and deterministic:
`CLAUDE_BIN` points at a fake CLI, so none of it costs a token. It pins the one property that
keeps the agent tests honest — a run that timed out or errored is reported as itself, once, rather
than as a handful of content assertions failing for a reason that has nothing to do with the skill.

### test-onboarding-skill.sh
Prose regressions in the onboarding skill, all by literal grep:
- `skills/onboarding/SKILL.md` stays thin and vendor-neutral — no tool names, no vendor
  directories, no absolute or Windows paths, no enum values
- it still points at `references/questions.yaml`, `references/rules.md`, the schemas and `volume.py`
- `.claude/skills/onboard/SKILL.md` stays a pointer with three bindings, not a second copy of the
  flow
- `references/rules.md` keeps the rules that stop silent damage: the overwrite guard, echo-before-write, an
  update is not a re-interview, the shipped examples are off limits, and the exact unit-conversion
  constants
- `references/questions.yaml` keeps the profile/program scope split

### test-onboarding-volume.sh
`skills/onboarding/scripts/volume.py` through its real command line:
- `--self-test` passes and covers all 720 enum combinations
- the worked case reproduces the `volume` block in `assets/examples/program.example.json` byte for byte —
  the shipped example doubles as the pinned fixture
- two identical runs produce identical output; muscles come back in canonical order
- usage errors exit 2, input errors exit 3, and an unknown gym type or missing experience is
  refused rather than guessed
- `--write` reads goal/days/session/split from the program block, adds the volume block, and
  leaves the program block untouched

### test-onboarding-agent.sh (integration)
Three prompts against a real agent: what onboarding writes, what must happen before the first
write, and what it does when a profile already exists and the person just says "set me up".
Non-deterministic by nature — assertions stay at keyword level.

### test-generation-skill.sh
Prose regressions in the generation skill, all by literal grep. Narrower than the onboarding
equivalent — the validator already scans this skill for vendor tool names, absolute paths and enum
tokens, so this file asserts only what is left over:
- `skills/generation/SKILL.md` stays portable and stays a set of pointers, holding no split names,
  muscle groups, order rules or tunable keys of its own
- `.claude/skills/generate/SKILL.md` stays a pointer with three bindings, not a second copy
- `references/rules.md` keeps the boundaries: `plans/` is the entire writable surface, `rules.md` is read and
  never written, it never re-interviews, and the dataset cache is never committed
- `references/rules.md` keeps one owner per number — targets are never computed here, and it hands back the
  exact `volume.py` command
- `references/rules.md` keeps the rules that stop a wrong plan: never fabricate exercises, the exact clone
  command, a missing plan beats a plausible wrong one, never drop a rule, never hide a shortfall,
  suffix rather than overwrite
- `docs/generation-fields.md` keeps the warning names, the ten muscle groups and all five order rules

### test-generation-script.sh
`skills/generation/scripts/generate.py` through its real command line:
- `--self-test` passes; its ten in-process invariants are not re-asserted here
- the worked case reproduces `assets/examples/plan.example.json` byte for byte from the bundled fixture —
  one `cmp` that pins selection, scoring, ordering, rounding and formatting at once (line endings
  aside: what the checkout holds depends on `core.autocrlf`, not on the generator)
- two identical runs produce identical output; targets come back in canonical order
- usage errors exit 2 and input errors exit 3; a plan is never overwritten
- every unknown value — dataset name, muscle, equipment tier, split, goal, rules key, order rule —
  is refused rather than guessed, and the message names the file to fix
- a hand-edited program file that is present but incomplete — an empty or partial volume block, an
  empty program block, a missing render-only key like `emoji` — is an input error naming the
  missing key, never a traceback and never a schema-invalid plan on disk
- unmatched rule entries are warnings, not failures, and reach both the JSON and the render
- the markdown render carries the volume table, each day, the deload note and the short flag

### test-generation-agent.sh (integration)
Three prompts against a real agent: what the skill writes and what it must leave alone, what must
be shown before the first plan file lands, and what it does when the dataset cannot be fetched.
Each probes a rule with no deterministic proxy elsewhere in the suite.

## Test helpers

`test-helpers.sh`. Two assertion families, named apart so they never shadow each other.

On captured output (case-insensitive regex — models capitalize freely):
- `run_claude "prompt" [timeout] [allowed_tools]` — returns the CLI's exit code and always puts
  whatever it captured on stdout, so a caller using `$(...)` can tell a bad answer from no answer.
  `CLAUDE_BIN` overrides the binary, which is how the harness test fakes a CLI.
- `assert_agent_responded "$?" "$output" "prompt name"` — guard an agent prompt before asserting on
  what it said; returns 0 when the run is worth asserting on
- `assert_contains "$output" pattern name`
- `assert_not_contains "$output" pattern name`
- `assert_count "$output" pattern count name`
- `assert_order "$output" pattern_a pattern_b name`

On files and exit codes (literal, case-sensitive; a missing file fails rather than passing
vacuously):
- `assert_file_contains "$file" "literal" name`
- `assert_file_not_contains "$file" "literal" name`
- `assert_exit_code expected actual name`

Fixtures:
- `create_test_project` → temp dir
- `cleanup_test_project "$dir"`
- `create_test_profile "$dir" "$repo_root"` → the shipped example profile plus a program file with
  no volume block, the state onboarding leaves behind before its last step

Every failing assertion increments `TESTS_FAILED`. End each file with `finish_tests`, which prints
`STATUS: PASSED` / `STATUS: FAILED (N failures)` and exits accordingly.

## Adding a test

1. Create `test-<skill>-<area>.sh`
2. Source `test-helpers.sh`, print a `=== Title ===` header, assert, call `finish_tests`
3. Add it to `tests=()` — or `integration_tests=()` — in `run-skill-tests.sh`

Use `set -uo pipefail`, not `-e`: a failing assertion must be counted, not abort the file.

### Writing tests on Windows

The shell translates POSIX paths in a command's arguments, but not inside a quoted `python -c`
body. Pass every path as an argv entry and read it from `sys.argv`, and open JSON with
`encoding='utf-8'` — the default codec on Windows mangles the emoji in a program file.

A generated plan carries that emoji through to stdout, so any invocation whose output you capture
needs `PYTHONIOENCODING=utf-8` or it dies on `UnicodeEncodeError` before printing anything. The
scripts' error messages contain em-dashes and the rendered volume table contains `×` and `⚠️`:
match the ASCII part of those lines and keep the punctuation out of grep patterns, which are bytes
and would otherwise depend on the test file's own encoding.
