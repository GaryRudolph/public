#!/usr/bin/env bash
# End-to-end check of the Makefile: install into a sandboxed $HOME with the
# repo's real plugins, then uninstall, and require the home to match its
# pre-install snapshot. Also checks that a second uninstall is a no-op and
# that switching every tool to plugin mode leaves nothing of ours behind.
#
# Required env: AGENTS_DIR

set -euo pipefail

: "${AGENTS_DIR:?AGENTS_DIR required}"
: "${ORG:?ORG required}"
# A skill every install has; <org>-standards carries the core.
SKILL="${ROUNDTRIP_SKILL:-$ORG-standards}"
MARK="# >>> $ORG >>>"

SB="$AGENTS_DIR/build/test-roundtrip"
H="$SB/home"
FAILED=0
fail() { printf 'FAIL: %s\n' "$1" >&2; FAILED=1; }

rm -rf "$SB"
mkdir -p "$H/.claude" "$H/.cursor" "$SB/projects"
printf 'my own notes\n' > "$H/.claude/CLAUDE.md"
printf '{\n  "theme": "dark"\n}\n' > "$H/.cursor/unrelated.json"

snapshot() {
    (cd "$H" && find . -print | LC_ALL=C sort | while IFS= read -r p; do
        if [ -L "$p" ]; then printf 'L %s -> %s\n' "$p" "$(readlink "$p")"
        elif [ -f "$p" ]; then printf 'F %s %s\n' "$p" "$(cksum < "$p")"
        else printf 'D %s\n' "$p"; fi
    done)
}

mk() {
    # A CLAUDE_BIN that does not exist keeps the local-marketplace pass off the real CLI.
    env HOME="$H" make -s -C "$AGENTS_DIR" "$@" \
        PROJECTS_DIR="$SB/projects" CLAUDE_BIN=no-such-claude REMOVE_HISTORY=yes WIN_HOME=
}

snapshot > "$SB/before.txt"

printf '=== roundtrip 1: default modes ===\n'
mk install > "$SB/install.out" 2>&1 || { cat "$SB/install.out"; fail "install failed"; }
grep -qF "$MARK" "$H/AGENTS.md" || fail "Cursor block missing after install"
if grep -qF "$MARK" "$H/.claude/CLAUDE.md"; then
    fail "CLAUDE_MODE=plugin (default) should not write a Claude block"
fi
[ -d "$H/.cursor/skills/$SKILL" ] || fail "Cursor skill copies missing"
[ -L "$H/.agents/skills/$SKILL" ] || fail "~/.agents/skills links missing"
[ ! -e "$H/.claude/skills/$SKILL" ] || fail "Claude skills should come from the plugin"

mk uninstall > "$SB/uninstall.out" 2>&1 || { cat "$SB/uninstall.out"; fail "uninstall failed"; }
snapshot > "$SB/after.txt"
diff "$SB/before.txt" "$SB/after.txt" > "$SB/diff.txt" || fail "home differs after uninstall (see $SB/diff.txt)"

mk uninstall > "$SB/uninstall-2.out" 2>&1 || fail "second uninstall failed"
snapshot > "$SB/after-2.txt"
cmp -s "$SB/after.txt" "$SB/after-2.txt" || fail "second uninstall changed the home"

printf '=== roundtrip 2: every tool in plugin mode ===\n'
mk install CLAUDE_MODE=plugin CODEX_MODE=plugin GEMINI_MODE=plugin CURSOR_MODE=plugin \
    > "$SB/install-plugin.out" 2>&1 || { cat "$SB/install-plugin.out"; fail "plugin-mode install failed"; }
for f in AGENTS.md .codex/AGENTS.md .gemini/GEMINI.md; do
    if [ -f "$H/$f" ] && grep -qF "$MARK" "$H/$f"; then
        fail "plugin mode left a block in $f"
    fi
done
for d in .cursor/skills .agents/skills .claude/skills; do
    if [ -d "$H/$d" ] && find "$H/$d" -mindepth 1 -maxdepth 1 -name "$ORG-*" | grep -q .; then
        fail "plugin mode left skills in $d"
    fi
done
[ -x "$H/.cursor/hooks/$ORG-enforce-denylist.sh" ] || fail "denylist hook belongs in every mode"
[ ! -e "$H/.cursor/hooks/$ORG-refresh-skills.sh" ] || fail "refresh hook is only for copy mode"
mk uninstall > /dev/null 2>&1 || fail "uninstall after plugin mode failed"
snapshot > "$SB/after-3.txt"
diff "$SB/before.txt" "$SB/after-3.txt" > "$SB/diff-3.txt" || fail "home differs after plugin-mode uninstall (see $SB/diff-3.txt)"

if [ "$FAILED" = "0" ]; then
    printf 'roundtrip-test: all checks passed\n'
    exit 0
fi
cat "$SB/diff.txt" "$SB/diff-3.txt" 2>/dev/null >&2 || true
exit 1
