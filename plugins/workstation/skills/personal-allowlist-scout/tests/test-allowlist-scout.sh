#!/usr/bin/env bash
# Tests for the allowlist scout. Needs only python3.
#   1. Render-then-scan unit tests (test_render_scan.py).
#   2. scan.py end to end, with the Claude config dirs passed through the
#      environment the way a routed session sees them.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
scan="$here/../scripts/scan.py"

python3 -I "$here/test_render_scan.py" || exit 1

fails=0
fail() { printf 'FAIL: %s\n' "$*"; fails=$((fails + 1)); }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Two repos with the same three targets; r1 also allows `make build` itself.
for r in r1 r2; do
    mkdir -p "$tmp/ws/$r/.git"
    printf 'test:\n\ttrue\nlint:\n\ttrue\nbuild:\n\ttrue\n' > "$tmp/ws/$r/Makefile"
done
mkdir -p "$tmp/ws/r1/.claude"
printf '{"permissions":{"allow":["Bash(make build:*)"]}}\n' > "$tmp/ws/r1/.claude/settings.json"

# Two routed dirs: lolay allows test and lint, agerpoint only lint.
claude_allow() {  # dir entries...
    local d=$1; shift
    mkdir -p "$d"
    python3 -I -c 'import json,sys; print(json.dumps({"permissions":{"allow":sys.argv[1:]}}))' "$@" \
        > "$d/settings.json"
}
claude_allow "$tmp/home/.claude-lolay" "Bash(make test:*)" "Bash(make lint:*)"
claude_allow "$tmp/home/.claude-agerpoint" "Bash(make lint:*)"
# The legacy ~/.claude allows everything, to show when it is (not) read.
claude_allow "$tmp/home/.claude" "Bash(make:*)"

run_scan() {  # extra env assignments...
    env -u CLAUDE_CONFIG_DIRS -u CLAUDE_CONFIG_DIR -u CLAUDE_DATA_HOME \
        HOME="$tmp/home" CURSOR_DATA_HOME="$tmp/home/.cursor" \
        GEMINI_DATA_HOME="$tmp/home/.gemini" "$@" \
        python3 -I "$scan" --no-summary "$tmp/ws"
}

# check <name> <json> <python expression over d, the scan result>
check() {
    printf '%s' "$2" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
def repo(name):
    return next(r for r in d["repos"] if r["name"] == name)
def claude_missing(name):
    return {e["segment"] for e in repo(name)["group1"] + repo(name)["group2"]
            if "claude" in e["missing_harnesses"]}
def promoted_claude():
    return {e["segment"] for e in d["global_promotion_candidates"]
            if "claude" in e["missing_global_harnesses"]}
sys.exit(0 if eval(sys.argv[1]) else 1)' "$3" || fail "$1: $3"
}

printf '[S1] two dirs: covered only when every dir allows it\n'
out=$(run_scan CLAUDE_CONFIG_DIRS="$tmp/home/.claude-lolay:$tmp/home/.claude-agerpoint") \
    || fail "S1: scan exited non-zero"
check S1 "$out" 'd["global_allowlists"]["claude"]["source"] == "CLAUDE_CONFIG_DIRS"'
check S1 "$out" '[x["count"] for x in d["global_allowlists"]["claude"]["dirs"]] == [2, 1]'
check S1 "$out" '"make test" in claude_missing("r1") and "make test" in claude_missing("r2")'
check S1 "$out" '"make lint" not in claude_missing("r1") | claude_missing("r2")'
check S1 "$out" '"make test" in promoted_claude() and "make lint" not in promoted_claude()'

printf '[S2] repo-only command: the repo file covers it under every dir\n'
check S2 "$out" '"make build" not in claude_missing("r1")'
check S2 "$out" '"make build" in claude_missing("r2")'

printf '[S3] no list: the session dir alone is the baseline\n'
out=$(run_scan CLAUDE_CONFIG_DIR="$tmp/home/.claude-lolay") || fail "S3: scan exited non-zero"
check S3 "$out" 'd["global_allowlists"]["claude"]["source"] == "CLAUDE_CONFIG_DIR"'
check S3 "$out" '"make test" not in claude_missing("r2") and "make lint" not in claude_missing("r2")'

printf '[S4] legacy single dir: ~/.claude when nothing is set; CLAUDE_DATA_HOME ignored\n'
out=$(run_scan CLAUDE_DATA_HOME="$tmp/home/.claude-agerpoint") || fail "S4: scan exited non-zero"
check S4 "$out" 'd["global_allowlists"]["claude"]["source"] == "default"'
check S4 "$out" 'd["global_allowlists"]["claude"]["dirs"][0]["path"].endswith("/home/.claude/settings.json")'
check S4 "$out" 'not claude_missing("r1") and not claude_missing("r2") and not promoted_claude()'

if [ "$fails" -ne 0 ]; then
    printf '%d allowlist-scout check(s) failed\n' "$fails"
    exit 1
fi
printf 'allowlist-scout end-to-end checks passed\n'
