#!/usr/bin/env bash
# Runs scripts/validate-skills.py as part of this suite, so run-skill-tests.sh
# is the single command that checks everything.
#
# The validator is wired in, not re-implemented. It hand-rolls a JSON Schema
# subset, a YAML parser and a frontmatter parser — none of which belong in
# bash — and it stays the sole owner of the static contracts: frontmatter
# shape, SKILL.md vendor-neutrality, every `stores:` path resolving against the
# schemas, the shipped examples validating, and volume.config.json covering
# every schema enum.
#
# --skills-only keeps the gitignored profiles/ out of it: they are user data no
# other machine has, and a hand-edited local profile must not fail a suite that
# runs clean everywhere else. Run the validator bare to check real profiles.
#
# It is silent on success and prints "FAIL: <what>" lines on failure, so the
# assertion below is the exit code and the output is the diagnosis.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

VALIDATOR="$REPO_ROOT/scripts/validate-skills.py"

echo "=== Repository Contracts ==="
echo ""

if [ ! -f "$VALIDATOR" ]; then
    _fail "scripts/validate-skills.py exists"
    finish_tests
fi

# Run from the repository root: the validator resolves its paths relative to
# its own location, but its output reads better from there.
out=$(cd "$REPO_ROOT" && python "$VALIDATOR" --skills-only 2>&1)
code=$?

assert_exit_code 0 "$code" "validate-skills.py reports no failures"
if [ "$code" -ne 0 ]; then
    echo "$out" | sed 's/^/    /'
fi

finish_tests
