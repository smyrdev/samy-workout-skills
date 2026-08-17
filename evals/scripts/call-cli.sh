#!/usr/bin/env bash
# call-cli.sh — the eval pipeline's one shell leaf.
#
#   call-cli.sh <timeout-seconds> <prompt-file> <response-file>
#
# Why this is shell (see the 2026-08-17 design spec): `timeout -k` makes the
# deadline real against a CLI that ignores SIGTERM, and bash resolves a
# CLAUDE_BIN that is a shebang script — which is exactly what the offline
# test fakes are. Everything else about judging lives in judge.py.
#
# Not `exec`: when `-k`'s grace period expires, `timeout` is itself killed
# by SIGKILL rather than exiting cleanly with 137, and on Windows a process
# genuinely killed by a signal reports a garbled exit code to a native
# (non-MSYS) waiter such as judge.py's `python`. Running `timeout` as a
# plain child and re-exiting with its already-decoded status keeps 124/137
# intact for that caller.
set -uo pipefail
CLI="${CLAUDE_BIN:-claude}"
timeout -k 10 "$1" "$CLI" -p --output-format json < "$2" > "$3" 2>&1
rc=$?
exit "$rc"
