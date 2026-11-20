#!/usr/bin/env bash
# Offline tests for personal-ship-pr's scripts: pr_state.py against a fake gh,
# and the PostToolUse hook. Needs only bash and python3.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
exec python3 -I "$here/test_ship_pr.py"
