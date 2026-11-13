#!/usr/bin/env bash
# make test-orchestrate: the orchestrate kit's offline tests. Usage: test-orchestrate.sh <plugin-root>
# Runs every suite even when one fails, so one failure can't hide the others' results.
set -uo pipefail
root=$1; org=$(basename "$root"); kit=$root/skills/$org-plan-orchestrate
[ -f "$kit/claude-workflows/plan-segment.js" ] || { echo "test-orchestrate: no kit in $kit, skipping"; exit 0; }
failed=()
suite() { local name=$1; shift; "$@" || failed+=("$name"); }
suite orchestrate_check.py python3 -I "$kit/tests/orchestrate_check.py" "$root"
suite test_plan_state.py python3 -I "$kit/tests/test_plan_state.py" "$kit/scripts"
suite test_check_wave.py python3 -I "$kit/tests/test_check_wave.py" "$kit/scripts"
suite test_orchestrate_gate.py python3 -I "$kit/tests/test_orchestrate_gate.py" "$kit/scripts"
suite test_token_tally.py python3 -I "$kit/tests/test_token_tally.py" "$kit/scripts" "$root/skills/$org-standards/standards/plan-execution.md"
if command -v node >/dev/null; then suite plan-segment-test.mjs node "$kit/tests/plan-segment-test.mjs" "$kit/claude-workflows/plan-segment.js"
else echo "SKIP plan-segment-test.mjs: node not installed"; fi
if [ "${#failed[@]}" -gt 0 ]; then
    printf 'test-orchestrate: %d suite(s) failed: %s\n' "${#failed[@]}" "${failed[*]}" >&2
    exit 1
fi
echo "test-orchestrate: all suites passed"
