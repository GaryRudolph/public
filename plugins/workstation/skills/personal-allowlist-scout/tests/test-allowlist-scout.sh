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

# Two routed dirs: lolay allows test and lint, agerpoint only lint. The
# personal ~/.claude allows test and build but not lint.
claude_allow() {  # dir entries...
    local d=$1; shift
    mkdir -p "$d"
    python3 -I -c 'import json,sys; print(json.dumps({"permissions":{"allow":sys.argv[1:]}}))' "$@" \
        > "$d/settings.json"
}
lolay="$tmp/home/.claude-lolay"
ap="$tmp/home/.claude-agerpoint"
claude_allow "$lolay" "Bash(make test:*)" "Bash(make lint:*)"
claude_allow "$ap" "Bash(make lint:*)"
claude_allow "$tmp/home/.claude" "Bash(make test:*)" "Bash(make build:*)"

run_scan() {  # extra env assignments...
    env -u CLAUDE_CONFIG_DIRS -u CLAUDE_CONFIG_DIR -u CLAUDE_DATA_HOME \
        -u CLAUDE_MANAGED_SETTINGS CLAUDE_MANAGED_SETTINGS_DIR="$tmp/os-none" \
        HOME="$tmp/home" CURSOR_DATA_HOME="$tmp/home/.cursor" \
        GEMINI_DATA_HOME="$tmp/home/.gemini" "$@" \
        python3 -I "$scan" --no-summary "$tmp/ws"
}

# check <name> <json> <python expression over d, the scan result>
check() {
    printf '%s' "$2" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
claude = d["global_allowlists"]["claude"]
def repo(name):
    return next(r for r in d["repos"] if r["name"] == name)
def claude_missing(name):
    return {e["segment"] for e in repo(name)["group1"] + repo(name)["group2"]
            if "claude" in e["missing_harnesses"]}
def promoted_claude():
    return {e["segment"] for e in d["global_promotion_candidates"]
            if "claude" in e["missing_global_harnesses"]}
def dir_names():
    return [x["path"].split("/")[-2] for x in claude["dirs"]]
sys.exit(0 if eval(sys.argv[1]) else 1)' "$3" || fail "$1: $3"
}

printf '[S1] two dirs: covered only when every dir allows it\n'
out=$(run_scan CLAUDE_CONFIG_DIRS="$lolay:$ap" CLAUDE_CONFIG_DIR="$lolay") \
    || fail "S1: scan exited non-zero"
check S1 "$out" 'claude["source"] == "CLAUDE_CONFIG_DIRS"'
check S1 "$out" 'dir_names() == [".claude-agerpoint", ".claude-lolay"]'
check S1 "$out" '[x["count"] for x in claude["dirs"]] == [1, 2]'
check S1 "$out" '"make test" in claude_missing("r1") and "make test" in claude_missing("r2")'
check S1 "$out" '"make lint" not in claude_missing("r1") | claude_missing("r2")'
check S1 "$out" '"make test" in promoted_claude() and "make lint" not in promoted_claude()'

printf '[S2] repo-only command: the repo file covers it under every dir\n'
check S2 "$out" '"make build" not in claude_missing("r1")'
check S2 "$out" '"make build" in claude_missing("r2")'

printf '[S3] no list: the session dir alone is the baseline\n'
out=$(run_scan CLAUDE_CONFIG_DIR="$lolay") || fail "S3: scan exited non-zero"
check S3 "$out" 'claude["source"] == "session" and dir_names() == [".claude-lolay"]'
check S3 "$out" '"make test" not in claude_missing("r2") and "make lint" not in claude_missing("r2")'

printf '[S4] legacy single dir: ~/.claude when nothing is set; CLAUDE_DATA_HOME ignored\n'
out=$(run_scan CLAUDE_DATA_HOME="$ap") || fail "S4: scan exited non-zero"
check S4 "$out" 'claude["source"] == "session" and dir_names() == [".claude"]'
check S4 "$out" '"make lint" in claude_missing("r2") and "make test" not in claude_missing("r2")'

printf '[S5] a personal session outside the list still counts its own dir\n'
out=$(run_scan CLAUDE_CONFIG_DIRS="$lolay:$ap") || fail "S5: scan exited non-zero"
check S5 "$out" 'dir_names() == [".claude-lolay", ".claude-agerpoint", ".claude"]'
check S5 "$out" '"make lint" in claude_missing("r2")'

printf '[S6] a listed dir missing on this machine is reported, not counted\n'
out=$(run_scan CLAUDE_CONFIG_DIRS="$tmp/home/.claude-gone:$lolay" CLAUDE_CONFIG_DIR="$lolay" 2>/dev/null) \
    || fail "S6: scan exited non-zero"
check S6 "$out" 'dir_names() == [".claude-lolay"]'
check S6 "$out" '[p.split("/")[-1] for p in claude["missing_dirs"]] == [".claude-gone"]'
check S6 "$out" '"make test" not in claude_missing("r2")'

printf '[S7] managed settings count for every dir (flag, env var, OS drop-in)\n'
managed="$tmp/managed.json"
printf '{"permissions":{"allow":["Bash(make test)","Bash(make lint)"]}}\n' > "$managed"
out=$(run_scan CLAUDE_CONFIG_DIRS="$lolay:$ap" CLAUDE_CONFIG_DIR="$lolay" \
    CLAUDE_MANAGED_SETTINGS="$managed") || fail "S7: scan exited non-zero"
check S7 "$out" '[m["count"] for m in claude["managed"]] == [2]'
check S7 "$out" '[x["count"] for x in claude["dirs"]] == [1, 2]'
check S7 "$out" '"make test" not in claude_missing("r2") and "make lint" not in claude_missing("r2")'
check S7 "$out" '"make build" in claude_missing("r2")'
out=$(run_scan CLAUDE_CONFIG_DIRS="$lolay:$ap" CLAUDE_CONFIG_DIR="$lolay" \
    CLAUDE_MANAGED_SETTINGS="$tmp/absent.json" 2>/dev/null) || fail "S7: absent file exited non-zero"
check S7 "$out" '[m["exists"] for m in claude["managed"]] == [False]'
check S7 "$out" '"make test" in claude_missing("r2")'
mkdir -p "$tmp/os/managed-settings.d"
cp "$managed" "$tmp/os/managed-settings.d/10-org.json"
out=$(run_scan CLAUDE_CONFIG_DIR="$tmp/home/.claude-none" CLAUDE_MANAGED_SETTINGS_DIR="$tmp/os") \
    || fail "S7: drop-in exited non-zero"
check S7 "$out" '"make test" not in claude_missing("r2")'

printf '[S8] no managed file: unchanged, and reported empty\n'
out=$(run_scan CLAUDE_CONFIG_DIR="$lolay") || fail "S8: scan exited non-zero"
check S8 "$out" 'claude["managed"] == []'

if [ "$fails" -ne 0 ]; then
    printf '%d allowlist-scout check(s) failed\n' "$fails"
    exit 1
fi
printf 'allowlist-scout end-to-end checks passed\n'
