#!/usr/bin/env bash
# make test-orchestrate: the orchestrate kit's offline tests. Usage: test-orchestrate.sh <plugin-root>
set -euo pipefail
root=$1; org=$(basename "$root"); kit=$root/skills/$org-plan-orchestrate
[ -f "$kit/claude-workflows/plan-segment.js" ] || { echo "test-orchestrate: no kit in $kit, skipping"; exit 0; }
python3 -I "$kit/tests/orchestrate_check.py" "$root"
python3 -I "$kit/tests/test_plan_state.py" "$kit/scripts"
python3 -I "$kit/tests/test_check_wave.py" "$kit/scripts"
python3 -I "$kit/tests/test_orchestrate_gate.py" "$kit/scripts"
python3 -I "$kit/tests/test_token_tally.py" "$kit/scripts" "$root/skills/$org-standards/standards/plan-execution.md"
if command -v node >/dev/null; then node "$kit/tests/plan-segment-test.mjs" "$kit/claude-workflows/plan-segment.js"
else echo "SKIP plan-segment-test.mjs: node not installed"; fi
