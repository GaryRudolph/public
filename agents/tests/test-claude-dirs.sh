#!/usr/bin/env bash
# CLAUDE_CONFIG_DIRS through the real Makefile, in a sandboxed $HOME: two dirs
# install and uninstall together (block, skills, local marketplace; install
# clears what an earlier version's allowlist left in each, and writes none),
# `make status` names a ~/.claude* dir the list leaves out, and a bad list is
# refused. Needs bash, make, jq and python3 (the installers' own floor).
#
# Required env: AGENTS_DIR, ORG

set -uo pipefail
# The real config dirs must stay out of the sandbox: the dotfiles export
# CLAUDE_CONFIG_DIRS, and the lib scripts and the Makefile default from it.
unset CLAUDE_CONFIG_DIRS CLAUDE_CONFIG_DIR

: "${AGENTS_DIR:?AGENTS_DIR required}"
: "${ORG:?ORG required}"
SKILL="${ROUNDTRIP_SKILL:-$ORG-standards}"
MARK="# >>> $ORG >>>"

SB="$AGENTS_DIR/build/test-claude-dirs"
H="$SB/home"
A="$H/.claude-a"
B="$H/.claude-b"
FAILED=0
ok()   { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; FAILED=1; }
check() { # description, then a command that must succeed
    local what="$1"; shift
    if "$@"; then ok "$what"; else fail "$what"; fi
}

rm -rf "$SB"
mkdir -p "$A" "$B" "$H/.cursor" "$SB/projects" "$SB/bin" "$SB/commands"
printf 'a slash command\n' > "$SB/commands/fake-command.md"
printf 'notes a\n' > "$A/CLAUDE.md"
printf 'notes b\n' > "$B/CLAUDE.md"

snapshot() {
    (cd "$H" && find . -print | LC_ALL=C sort | while IFS= read -r p; do
        if [ -L "$p" ]; then printf 'L %s -> %s\n' "$p" "$(readlink "$p")"
        elif [ -f "$p" ]; then printf 'F %s %s\n' "$p" "$(cksum < "$p")"
        else printf 'D %s\n' "$p"; fi
    done)
}

# A claude stand-in that records the config dir each call ran against and
# reports nothing registered, so the marketplace pass would add and install.
cat > "$SB/bin/claude" <<'STUB'
#!/usr/bin/env bash
case "$*" in
    "plugin marketplace list --json"|"plugin list --json") echo '[]' ;;
    *) printf '%s: %s\n' "${CLAUDE_CONFIG_DIR:-unset}" "$*" >> "$STUB_LOG" ;;
esac
STUB
chmod +x "$SB/bin/claude"

mk() {
    env HOME="$H" STUB_LOG="$SB/claude-calls.log" make -s -C "$AGENTS_DIR" "$@" \
        PROJECTS_DIR="$SB/projects" REMOVE_HISTORY=yes WIN_HOME= COMMANDS_SRC="$SB/commands" \
        CLAUDE_BIN="$SB/bin/claude"
}

snapshot > "$SB/before.txt"
LIST="$A:$B"

printf 'two dirs install together\n'
mk install CLAUDE_MODE=home CLAUDE_CONFIG_DIRS="$LIST" > "$SB/install.out" 2>&1 \
    || { cat "$SB/install.out" >&2; fail "install failed"; }
for d in "$A" "$B"; do
    n=${d##*/}
    check "$n: block in CLAUDE.md" grep -qF "$MARK" "$d/CLAUDE.md"
    check "$n: its own notes kept" grep -qF "notes ${n#.claude-}" "$d/CLAUDE.md"
    check "$n: skills linked" test -L "$d/skills/$SKILL"
    check "$n: command linked" test -L "$d/commands/fake-command.md"
    check "$n: no settings.json written (managed settings carry the rules)" test ! -e "$d/settings.json"
done
check "the default ~/.claude was not created" test ! -e "$H/.claude"

printf 'local marketplace runs per dir\n'
: > "$SB/claude-calls.log"
mk install-local-marketplace CLAUDE_CONFIG_DIRS="$LIST" > "$SB/market.out" 2>&1 \
    || { cat "$SB/market.out" >&2; fail "install-local-marketplace failed"; }
for d in "$A" "$B"; do
    check "${d##*/}: marketplace added against this dir" \
        grep -qF "$d: plugin marketplace add" "$SB/claude-calls.log"
done

printf 'status names the dirs it does not manage\n'
mkdir -p "$H/.claude-x"
printf '{}\n' > "$H/.claude.json"
mk status CLAUDE_MODE=home CLAUDE_CONFIG_DIRS="$LIST" > "$SB/status.out" 2>&1 \
    || { cat "$SB/status.out" >&2; fail "status failed"; }
check "unlisted ~/.claude-x is named"  grep -qE '\.claude-x +\? not managed' "$SB/status.out"
check "listed .claude-a is managed"    grep -qE '\.claude-a +OK managed' "$SB/status.out"
check "listed .claude-b is managed"    grep -qE '\.claude-b +OK managed' "$SB/status.out"
check "listed dirs are not flagged"    test "$(grep -c 'not managed' "$SB/status.out")" = 1
check "a ~/.claude.json file is not a dir" test "$(grep -c 'claude.json' "$SB/status.out")" = 0
check "blocks status reports both dirs" \
    test "$(grep -cE '\.claude-[ab]/CLAUDE.md' "$SB/status.out")" -ge 2

mk status-claude-dirs CLAUDE_CONFIG_DIRS="$A:$A/:$B:" > "$SB/status-dup.out" 2>&1
check "a repeated dir is listed once" test "$(grep -c '\.claude-a ' "$SB/status-dup.out")" = 1
mk status-claude-dirs CLAUDE_CONFIG_DIRS="/tmp/a%:/tmp/abc" > "$SB/status-pct.out" 2>&1
check "a '%' in one path doesn't drop another dir" \
    test "$(grep -c 'listed but not found' "$SB/status-pct.out")" = 2
mk status-claude-dirs CLAUDE_CONFIG_DIRS="$A///:$A:$B//" > "$SB/status-slash.out" 2>&1
check "repeated trailing slashes are trimmed and deduplicated" \
    test "$(grep -c 'OK managed' "$SB/status-slash.out")" = 2
mk status-claude-dirs CLAUDE_CONFIG_DIRS="///" > "$SB/status-root.out" 2>&1
check "a lone / stays /" grep -qE '^/ +OK managed' "$SB/status-root.out"
check "a trailing colon adds no dir" test "$(grep -c 'OK managed' "$SB/status-dup.out")" = 2
ln -s "$A" "$H/.claude-link"
mk status-claude-dirs CLAUDE_CONFIG_DIRS="$A:$B" > "$SB/status-link.out" 2>&1
check "a symlink to a listed dir is not reported as unmanaged" \
    test "$(grep -c '\.claude-link' "$SB/status-link.out")" = 0
rm -f "$H/.claude-link"
mk status-claude-dirs CLAUDE_CONFIG_DIRS="$A" > "$SB/status-left.out" 2>&1
check "an unlisted dir that still holds our files says so" \
    grep -qE "\.claude-b +\? not managed.*still holds $ORG files" "$SB/status-left.out"
rmdir "$H/.claude-x"
mkdir -p "$H/.claude"
mk status-claude-dirs > "$SB/status-default.out" 2>&1
check "default list is ~/.claude" grep -qE '\.claude +OK managed' "$SB/status-default.out"
check "default list leaves ~/.claude-a unmanaged" \
    grep -qE '\.claude-a +\? not managed' "$SB/status-default.out"
rmdir "$H/.claude"

printf 'a path with a space\n'
SPD="$SB/sp ace/.claude-s"
mkdir -p "$SPD"
printf 'spaced notes\n' > "$SPD/CLAUDE.md"
before_sp=$(cd "$SPD" && find . -print | LC_ALL=C sort)
mk install CLAUDE_MODE=home CLAUDE_CONFIG_DIRS="$SPD" > "$SB/install-sp.out" 2>&1 \
    || { cat "$SB/install-sp.out" >&2; fail "install into a dir with a space failed"; }
check "block written into the dir with a space" grep -qF "$MARK" "$SPD/CLAUDE.md"
check "skills linked into the dir with a space" test -L "$SPD/skills/$SKILL"
mk uninstall CLAUDE_MODE=home CLAUDE_CONFIG_DIRS="$SPD" > "$SB/uninstall-sp.out" 2>&1 \
    || { cat "$SB/uninstall-sp.out" >&2; fail "uninstall from a dir with a space failed"; }
check "the dir with a space is back to its notes" \
    test "$(cd "$SPD" && find . -print | LC_ALL=C sort)" = "$before_sp"
HSP="$SB/home sp"
mkdir -p "$HSP"
if env HOME="$HSP" make -s -C "$AGENTS_DIR" status-claude-dirs > "$SB/home-sp.out" 2>&1; then
    check "a HOME with a space still works" grep -q "claude config dirs" "$SB/home-sp.out"
else
    cat "$SB/home-sp.out" >&2; fail "make fails when HOME has a space"
fi

printf 'two dirs uninstall together\n'
mk uninstall CLAUDE_MODE=home CLAUDE_CONFIG_DIRS="$LIST" > "$SB/uninstall.out" 2>&1 \
    || { cat "$SB/uninstall.out" >&2; fail "uninstall failed"; }
rm -f "$H/.claude.json"
snapshot > "$SB/after.txt"
if diff "$SB/before.txt" "$SB/after.txt" > "$SB/diff.txt"; then
    ok "home matches its pre-install snapshot"
else
    cat "$SB/diff.txt" >&2; fail "home differs after uninstall (see $SB/diff.txt)"
fi

printf 'a bad list is refused\n'
if mk status-modes CLAUDE_CONFIG_DIRS="relative/dir" > "$SB/bad.out" 2>&1; then
    fail "a relative path should be refused"
else
    check "relative path named in the error" grep -q "absolute paths, got 'relative/dir'" "$SB/bad.out"
fi

if mk status-modes CLAUDE_CONFIG_DIRS="/tmp/@SP@foo:/tmp/bar" > "$SB/tok.out" 2>&1; then
    fail "the space placeholder in a path should be refused"
else
    check "the placeholder is named in the error" grep -q "can't contain '@SP@'" "$SB/tok.out"
fi

if mk status-modes CLAUDE_HOME="$A" > "$SB/old.out" 2>&1; then
    fail "the retired CLAUDE_HOME should be refused, not ignored"
else
    check "retired CLAUDE_HOME names its replacement" grep -q "CLAUDE_HOME is gone; set CLAUDE_CONFIG_DIRS" "$SB/old.out"
fi

if [ "$FAILED" = "0" ]; then
    printf 'test-claude-dirs: all checks passed\n'
    exit 0
fi
exit 1
