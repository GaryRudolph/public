#!/usr/bin/env bash
# Tests for scripts/session-start.sh: every part fits Claude Code's 10,000-
# character hook cap, hooks.json asks for more parts than core.md needs, the
# parts together carry all of core.md, and a part that starts inside a
# section names it. Needs bash and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
core="$root/skills/personal-standards/core.md"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }

# A HOME with no personal block, so the hook prints instead of staying silent.
mkdir -p "$work/home"
asked=$(python3 -I -c 'import json, sys
hooks = json.load(open(sys.argv[1]))["hooks"]["SessionStart"][0]["hooks"]
print(sum("session-start.sh" in h["command"] for h in hooks))' "$root/hooks/hooks.json")

needed=0
for part in $(seq 1 "$asked"); do
    HOME="$work/home" CLAUDE_PLUGIN_ROOT="$root" bash "$root/scripts/session-start.sh" "$part" > "$work/part$part"
    [ -s "$work/part$part" ] && needed=$part
done

if [ "$needed" -ge 1 ] && [ "$needed" -lt "$asked" ]; then
    pass "hooks.json asks for $asked parts; core needs $needed"
else
    fail "hooks.json asks for $asked parts but core needs $needed: add entries before a part goes unloaded"
fi

for part in $(seq 1 "$needed"); do
    chars=$(python3 -I -c 'import sys; print(len(open(sys.argv[1], encoding="utf-8").read()))' "$work/part$part")
    if [ "$chars" -le 10000 ]; then pass "part $part fits the hook cap ($chars characters)"; else fail "part $part is $chars characters, over 10,000"; fi
    if head -1 "$work/part$part" | grep -qF "part $part of $needed"; then pass "part $part names its place"; else fail "part $part header"; fi
done

# Strip each part's header and any "(continued)" heading; what's left, in
# part order, must be core.md exactly.
python3 -I - "$core" "$needed" "$work" <<'PY' && pass "the parts carry all of core.md" || fail "the parts don't add up to core.md"
import sys
core, needed, work = sys.argv[1], int(sys.argv[2]), sys.argv[3]
body = ""
for n in range(1, needed + 1):
    text = open(f"{work}/part{n}", encoding="utf-8").read()
    text = text.split("\n\n", 1)[1]
    if text.startswith("## ") and text.split("\n", 1)[0].endswith(" (continued)"):
        text = text.split("\n\n", 1)[1]
    body += text
sys.exit(0 if body == open(core, encoding="utf-8").read() else 1)
PY

for part in $(seq 2 "$needed"); do
    first=$(sed -n '3p' "$work/part$part")
    case "$first" in
        "## "*) pass "part $part opens on a section heading" ;;
        *) fail "part $part opens mid-section without a heading: $first" ;;
    esac
done

[ "$failures" -eq 0 ] && echo "all session-start tests passed" || { echo "$failures session-start test(s) failed" >&2; exit 1; }
