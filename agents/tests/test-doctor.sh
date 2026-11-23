#!/usr/bin/env bash
# Tests for this repo's own doctor: the root triage.yaml declares the toolchain
# floors, `make -C agents doctor` runs it, and the session doctor picks it.
# Runs triage itself only when it is installed. Needs bash, git, and python3.
set -uo pipefail
# The real config dirs must stay out of the sandbox: the dotfiles export
# CLAUDE_CONFIG_DIRS, and the lib scripts and the Makefile default from it.
unset CLAUDE_CONFIG_DIRS CLAUDE_CONFIG_DIR

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
work=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
config="$repo/triage.yaml"

printf 'triage.yaml\n'
[ -f "$config" ] && pass "the repo root has a triage.yaml" || fail "no triage.yaml at the repo root"
# tool floor severity: each floor is an error (no severity) and each optional tool a warning.
for want in "python3 >=3.9" "git >=2.28" "jq >=1.6" "make >=3.81" "claude >=2.1.273"; do
    tool=${want% *} floor=${want#* }
    if python3 - "$config" "$tool" "$floor" <<'PY'
import re, sys
text, tool, floor = open(sys.argv[1]).read(), sys.argv[2], sys.argv[3]
m = re.search(rf"- tool: {re.escape(tool)}\n((?:\s+[a-z_]+:.*\n)*)", text)
assert m, "tool not listed"
assert f'version: "{floor}"' in m.group(1), "floor missing"
assert "severity" not in m.group(1), "a floor must be an error, not a warning"
PY
    then pass "$tool: error below $floor"; else fail "$tool: no error floor of $floor in triage.yaml"; fi
done
for tool in sops age node; do
    if python3 - "$config" "$tool" <<'PY'
import re, sys
m = re.search(rf"- tool: {sys.argv[2]}\n((?:\s+[a-z_]+:.*\n)*)", open(sys.argv[1]).read())
assert m and "severity: warn" in m.group(1)
PY
    then pass "$tool: warning when missing"; else fail "$tool: not a warning in triage.yaml"; fi
done

printf 'make doctor\n'
grep -qE '^doctor:' "$repo/agents/Makefile" && pass "agents/Makefile defines a doctor target" || fail "no doctor target in agents/Makefile"
if command -v triage >/dev/null 2>&1; then
    make -s -C "$repo/agents" doctor >"$work/out" 2>&1; rc=$?
    [ "$rc" = 0 ] && pass "doctor passes on this machine (floors met)" || { fail "doctor exit $rc"; sed 's/^/        /' "$work/out" >&2; }
    for tool in python3 git jq make claude sops age node; do
        grep -q "$tool" "$work/out" && pass "  ...checks $tool" || fail "  ...does not check $tool"
    done
    # A floor above the installed version is an error (exit 1), not a warning.
    sed 's/">=3.9"/">=99"/' "$config" > "$work/high.yaml"
    (cd "$repo" && triage "$work/high.yaml" --no-update-check --no-color >"$work/out" 2>&1); rc=$?
    [ "$rc" != 0 ] && grep -q 'need >=99' "$work/out" && pass "python3 below its floor: an error" || fail "python3 below the floor didn't fail (exit $rc)"
else
    printf '  skip  triage not installed (brew install lolay/tap/triage)\n'
fi

printf 'session doctor\n'
if python3 -I - "$repo/plugins/personal/scripts/session-doctor.py" "$repo" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("session_doctor", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.doctor_command(Path(sys.argv[2])) == ["triage", "--profile", "default"], module.doctor_command(Path(sys.argv[2]))
PY
then pass "the session doctor runs triage --profile default at the repo root"; else fail "the session doctor picks another doctor for the repo root"; fi

if [ "$failures" -gt 0 ]; then
    printf '%d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'all doctor tests passed\n'
