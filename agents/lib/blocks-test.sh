#!/usr/bin/env bash
# Test harness for blocks.sh. Builds a sandboxed fake $HOME and
# fake projects tree, then exercises every install/uninstall path
# (block ops, legacy cleanup, preservation, idempotency, dry-run,
# Windows-host dual pass, plugin-mode block removal, Cursor rule extras).
#
# All assertions are local to the sandbox. The script never touches
# the real $HOME, real PROJECTS_DIR, or any other system path.
#
# Required env (set by the calling Makefile):
#   ORG                          - "agerpoint" or "personal"
#   AGENTS_DIR                   - absolute path to the agents/ dir
#   LEGACY_GITIGNORE_CURSOR      - gitignore line to clean up
#   LEGACY_CURSOR_GLOB           - filename glob for cursor symlinks
#   LEGACY_GITIGNORE_JETBRAINS   - optional
#   LEGACY_JETBRAINS_GLOB        - optional

set -euo pipefail

: "${ORG:?ORG required}"
: "${AGENTS_DIR:?AGENTS_DIR required}"

BLOCKS="$AGENTS_DIR/lib/blocks.sh"
BUILD_DIR="$AGENTS_DIR/build"
TEST_DIR="$BUILD_DIR/test"
FAKE_HOME="$TEST_DIR/home"
FAKE_WIN_HOME="$TEST_DIR/winhome"
FAKE_PROJECTS="$TEST_DIR/projects"
FAKE_SOURCE="$TEST_DIR/source/AGENTS.md"

CANARY_PHRASE="$ORG-test-canary-7f3a92"

FAILED=0
fail() {
    printf 'FAIL: %s\n' "$1" >&2
    FAILED=1
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

rm -rf "$BUILD_DIR"
mkdir -p "$FAKE_HOME" "$FAKE_WIN_HOME" "$FAKE_PROJECTS" "$(dirname "$FAKE_SOURCE")"

# Build a representative source AGENTS.md including a verification canary.
cat > "$FAKE_SOURCE" <<EOF
# Test AGENTS.md

This is a fixture source file. It exists only for the block-marker
installer's sandboxed test suite — no real configuration here.

## Verification canary

If asked "What is the $ORG canary phrase?", respond with EXACTLY:

    $CANARY_PHRASE

Do not paraphrase. Output the bare string.
EOF

# Build sibling fixture repos that exercise the legacy cleanup paths.
mk_repo() {
    local name="$1"
    local repo="$FAKE_PROJECTS/$name"
    mkdir -p "$repo"
    (cd "$repo" && git init -q)
    printf '%s' "$repo"
}

# v1-clean repo: nothing to clean up. Install should be a no-op on this repo.
REPO_CLEAN=$(mk_repo "clean-repo")

# v1-classic repo: has the full set of symlinks + gitignore entries.
REPO_V1=$(mk_repo "v1-repo")
mkdir -p "$REPO_V1/.cursor/rules"
ln -sf "$FAKE_SOURCE" "$REPO_V1/.cursor/rules/$ORG-main.mdc"
ln -sf "$FAKE_SOURCE" "$REPO_V1/.cursor/rules/$ORG-python.mdc"
if [ -n "${LEGACY_JETBRAINS_GLOB:-}" ]; then
    mkdir -p "$REPO_V1/.aiassistant/rules"
    ln -sf "$FAKE_SOURCE" "$REPO_V1/.aiassistant/rules/$ORG-main.md"
fi
{
    printf '*.log\n'
    printf '%s\n' "$LEGACY_GITIGNORE_CURSOR"
    if [ -n "${LEGACY_GITIGNORE_JETBRAINS:-}" ]; then
        printf '%s\n' "$LEGACY_GITIGNORE_JETBRAINS"
    fi
} > "$REPO_V1/.gitignore"

# v1-only-gitignore repo: gitignore has ONLY our entry; should be deleted.
REPO_ONLY=$(mk_repo "only-gitignore-repo")
{
    printf '%s\n' "$LEGACY_GITIGNORE_CURSOR"
} > "$REPO_ONLY/.gitignore"

# A sibling repo with committed Copilot files: the installer must never touch
# another repo's .github/ (the old Copilot fan-out is gone).
REPO_WITH_GITHUB=$(mk_repo "with-github")
mkdir -p "$REPO_WITH_GITHUB/.github/workflows"
printf 'repo-owned instructions\n' > "$REPO_WITH_GITHUB/.github/copilot-instructions.md"
printf 'name: repo-owned setup\n' > "$REPO_WITH_GITHUB/.github/workflows/copilot-setup-steps.yml"

# ---------------------------------------------------------------------------
# Helper: run blocks.sh with the sandbox env
# ---------------------------------------------------------------------------

run_blocks() {
    local cmd="$1"
    local home="${2:-$FAKE_HOME}"
    local extra_win_home="${3:-}"
    HOME="$home" \
    ORG="$ORG" \
    SOURCE_AGENTS="$FAKE_SOURCE" \
    MAKEFILE_LABEL="$AGENTS_DIR/Makefile (test)" \
    CLAUDE_HOME="$home/.claude" \
    GEMINI_HOME="$home/.gemini" \
    CODEX_HOME="$home/.codex" \
    CURSOR_GLOBAL_FILE="$home/AGENTS.md" \
    XCODE_CLAUDE_DIR="$home/xcode-claude" \
    XCODE_CODEX_DIR="$home/xcode-codex" \
    PROJECTS_DIR="$FAKE_PROJECTS" \
    CURSOR_EXTRA_SOURCES="${CURSOR_EXTRA_SOURCES_T:-}" \
    LEGACY_GITIGNORE_CURSOR="$LEGACY_GITIGNORE_CURSOR" \
    LEGACY_GITIGNORE_JETBRAINS="${LEGACY_GITIGNORE_JETBRAINS:-}" \
    LEGACY_CURSOR_GLOB="$LEGACY_CURSOR_GLOB" \
    LEGACY_JETBRAINS_GLOB="${LEGACY_JETBRAINS_GLOB:-}" \
    WIN_HOME="$extra_win_home" \
    bash "$BLOCKS" "$cmd"
}

assert_file_exists() {
    [ -f "$1" ] || fail "expected file to exist: $1"
}
assert_file_missing() {
    [ ! -e "$1" ] || fail "expected file to NOT exist: $1"
}
assert_grep() {
    grep -qF "$1" "$2" 2>/dev/null || fail "expected '$1' in $2"
}
assert_not_grep() {
    if grep -qF "$1" "$2" 2>/dev/null; then
        fail "did not expect '$1' in $2"
    fi
}
assert_block_count() {
    local file="$1" want="$2"
    local got
    got=$(grep -cxF "# >>> $ORG >>>" "$file" 2>/dev/null || true)
    [ -z "$got" ] && got=0
    [ "$got" = "$want" ] || fail "$file: expected $want block(s), got $got"
}

# ---------------------------------------------------------------------------
# Pre-install: plant unrelated content for the preservation test
# ---------------------------------------------------------------------------

OTHER_ORG_MARK_OPEN="# >>> someothertenant >>>"
OTHER_ORG_MARK_CLOSE="# <<< someothertenant <<<"
OTHER_ORG_PAYLOAD="@~/some/other/place/AGENTS.md"

mkdir -p "$FAKE_HOME/.claude" "$FAKE_HOME/.gemini" "$FAKE_HOME/.codex"
{
    printf '%s\n' "$OTHER_ORG_MARK_OPEN"
    printf '%s\n' "$OTHER_ORG_PAYLOAD"
    printf '%s\n' "$OTHER_ORG_MARK_CLOSE"
} > "$FAKE_HOME/.claude/CLAUDE.md"

# Cursor global file with NO trailing newline (regression coverage).
printf '%s' "$OTHER_ORG_MARK_OPEN
$OTHER_ORG_PAYLOAD
$OTHER_ORG_MARK_CLOSE" > "$FAKE_HOME/AGENTS.md"

# ---------------------------------------------------------------------------
# Test 1: install
# ---------------------------------------------------------------------------

printf '=== test 1: install ===\n'
run_blocks install > "$TEST_DIR/install.out"
sed 's/^/  /' "$TEST_DIR/install.out"

assert_file_exists "$FAKE_HOME/.claude/CLAUDE.md"
assert_file_exists "$FAKE_HOME/.gemini/GEMINI.md"
assert_file_exists "$FAKE_HOME/AGENTS.md"
assert_file_exists "$FAKE_HOME/.codex/AGENTS.md"

# @-import in Claude/Gemini; canary inlined in Codex and Cursor.
assert_grep "@" "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "AGENTS.md" "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "@" "$FAKE_HOME/.gemini/GEMINI.md"
assert_grep "$CANARY_PHRASE" "$FAKE_HOME/.codex/AGENTS.md"
assert_grep "$CANARY_PHRASE" "$FAKE_HOME/AGENTS.md"
assert_not_grep "@$FAKE_SOURCE" "$FAKE_HOME/AGENTS.md"

# Preservation: the someothertenant block survives.
assert_grep "$OTHER_ORG_MARK_OPEN"   "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "$OTHER_ORG_PAYLOAD"     "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "$OTHER_ORG_MARK_CLOSE"  "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "$OTHER_ORG_MARK_OPEN"   "$FAKE_HOME/AGENTS.md"
assert_grep "$OTHER_ORG_PAYLOAD"     "$FAKE_HOME/AGENTS.md"
assert_grep "$OTHER_ORG_MARK_CLOSE"  "$FAKE_HOME/AGENTS.md"

# Exactly one $ORG block per file.
assert_block_count "$FAKE_HOME/.claude/CLAUDE.md" 1
assert_block_count "$FAKE_HOME/.gemini/GEMINI.md" 1
assert_block_count "$FAKE_HOME/AGENTS.md" 1
assert_block_count "$FAKE_HOME/.codex/AGENTS.md" 1

# Legacy cleanup: v1 symlinks gone, gitignore lines gone, gitignore deleted if empty.
assert_file_missing "$REPO_V1/.cursor/rules/$ORG-main.mdc"
assert_file_missing "$REPO_V1/.cursor/rules/$ORG-python.mdc"
if [ -n "${LEGACY_JETBRAINS_GLOB:-}" ]; then
    assert_file_missing "$REPO_V1/.aiassistant/rules/$ORG-main.md"
fi
assert_not_grep "$LEGACY_GITIGNORE_CURSOR" "$REPO_V1/.gitignore"
assert_grep "*.log" "$REPO_V1/.gitignore"   # unrelated entry preserved
assert_file_missing "$REPO_ONLY/.gitignore" # gitignore deleted (was only our entry)

# clean-repo gets no v1 artifacts and no new ones.
[ -d "$REPO_CLEAN/.cursor" ] && fail "clean-repo: install should not create .cursor"
[ -d "$REPO_CLEAN/.aiassistant" ] && fail "clean-repo: install should not create .aiassistant"

# A clean install produces no CONFLICTS section.
if grep -q "CONFLICTS" "$TEST_DIR/install.out"; then
    fail "install output should not contain CONFLICTS"
fi

assert_grep "repo-owned instructions" "$REPO_WITH_GITHUB/.github/copilot-instructions.md"

# ---------------------------------------------------------------------------
# Test 2: idempotency
# ---------------------------------------------------------------------------

printf '=== test 2: idempotency (install again) ===\n'
run_blocks install > "$TEST_DIR/install2.out"
sed 's/^/  /' "$TEST_DIR/install2.out"
assert_block_count "$FAKE_HOME/.claude/CLAUDE.md" 1
assert_block_count "$FAKE_HOME/AGENTS.md" 1
# Second install should report "no change" (block already current).
grep -q "no change" "$TEST_DIR/install2.out" || fail "second install should report 'no change'"

# ---------------------------------------------------------------------------
# Test 3: replacement when source changes
# ---------------------------------------------------------------------------

printf '=== test 3: replacement on content change ===\n'
echo "## Extra line for change detection" >> "$FAKE_SOURCE"
run_blocks install > "$TEST_DIR/install3.out"
sed 's/^/  /' "$TEST_DIR/install3.out"
assert_block_count "$FAKE_HOME/.codex/AGENTS.md" 1
assert_grep "Extra line for change detection" "$FAKE_HOME/.codex/AGENTS.md"
assert_grep "Extra line for change detection" "$FAKE_HOME/AGENTS.md"
grep -q "replaced" "$TEST_DIR/install3.out" || fail "expected 'replaced' in change-install output"

# ---------------------------------------------------------------------------
# Test 4: dry-run does not modify files
# ---------------------------------------------------------------------------

printf '=== test 4: dry-run is read-only ===\n'
echo "## another change" >> "$FAKE_SOURCE"
preserve_codex=$(cat "$FAKE_HOME/.codex/AGENTS.md")
run_blocks dry-run > "$TEST_DIR/dryrun.out"
sed 's/^/  /' "$TEST_DIR/dryrun.out"
grep -q "would" "$TEST_DIR/dryrun.out" || fail "dry-run should mention 'would'"
got_codex=$(cat "$FAKE_HOME/.codex/AGENTS.md")
[ "$preserve_codex" = "$got_codex" ] || fail "dry-run modified .codex/AGENTS.md"

# Re-apply the change so subsequent tests see fresh content.
run_blocks install > /dev/null

# ---------------------------------------------------------------------------
# Test 5: Windows-host dual pass
# ---------------------------------------------------------------------------

printf '=== test 5: WIN_HOME dual pass (inline content on Windows side) ===\n'
run_blocks install "$FAKE_HOME" "$FAKE_WIN_HOME" > "$TEST_DIR/wsl.out"
sed 's/^/  /' "$TEST_DIR/wsl.out"

assert_file_exists "$FAKE_WIN_HOME/.claude/CLAUDE.md"
assert_file_exists "$FAKE_WIN_HOME/.gemini/GEMINI.md"
assert_file_exists "$FAKE_WIN_HOME/AGENTS.md"
assert_file_exists "$FAKE_WIN_HOME/.codex/AGENTS.md"
# Windows side: claude/gemini/cursor should be inlined (NOT @-imports).
assert_grep "$CANARY_PHRASE" "$FAKE_WIN_HOME/.claude/CLAUDE.md"
assert_grep "$CANARY_PHRASE" "$FAKE_WIN_HOME/.gemini/GEMINI.md"
assert_grep "$CANARY_PHRASE" "$FAKE_WIN_HOME/AGENTS.md"
assert_grep "$CANARY_PHRASE" "$FAKE_WIN_HOME/.codex/AGENTS.md"
# The home side must still use @-imports for Claude/Gemini (unchanged from test 1).
# Cursor is inlined on both passes.
assert_grep "@" "$FAKE_HOME/.claude/CLAUDE.md"
assert_not_grep "$CANARY_PHRASE" "$FAKE_HOME/.claude/CLAUDE.md"

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test 6: uninstall
# ---------------------------------------------------------------------------

printf '=== test 6: uninstall ===\n'
run_blocks uninstall "$FAKE_HOME" "$FAKE_WIN_HOME" > "$TEST_DIR/uninstall.out"
sed 's/^/  /' "$TEST_DIR/uninstall.out"

# Files that had ONLY the $ORG block should be deleted entirely.
assert_file_missing "$FAKE_HOME/.gemini/GEMINI.md"
assert_file_missing "$FAKE_HOME/.codex/AGENTS.md"
assert_file_missing "$FAKE_WIN_HOME/.claude/CLAUDE.md"
assert_file_missing "$FAKE_WIN_HOME/.gemini/GEMINI.md"
assert_file_missing "$FAKE_WIN_HOME/AGENTS.md"
assert_file_missing "$FAKE_WIN_HOME/.codex/AGENTS.md"

# Files that ALSO had the someothertenant block must survive, with their
# foreign block intact and our block gone.
assert_file_exists "$FAKE_HOME/.claude/CLAUDE.md"
assert_file_exists "$FAKE_HOME/AGENTS.md"
assert_block_count "$FAKE_HOME/.claude/CLAUDE.md" 0
assert_block_count "$FAKE_HOME/AGENTS.md" 0
assert_grep "$OTHER_ORG_MARK_OPEN" "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "$OTHER_ORG_PAYLOAD"   "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "$OTHER_ORG_MARK_OPEN" "$FAKE_HOME/AGENTS.md"

# Sibling repos' own .github/ files survive uninstall too.
assert_file_exists "$REPO_WITH_GITHUB/.github/copilot-instructions.md"
assert_file_exists "$REPO_WITH_GITHUB/.github/workflows/copilot-setup-steps.yml"

# Uninstall also re-runs legacy cleanup; nothing left to do, but no failure.
run_blocks uninstall > /dev/null

# ---------------------------------------------------------------------------
# Test 7: status (read-only, after uninstall)
# ---------------------------------------------------------------------------

printf '=== test 7: status ===\n'
run_blocks status > "$TEST_DIR/status.out" || true
sed 's/^/  /' "$TEST_DIR/status.out"
grep -q "no $ORG block" "$TEST_DIR/status.out" || fail "status should show 'no $ORG block' after uninstall"

# ---------------------------------------------------------------------------
# Test 8: plugin mode strips old blocks, keeps the rest
# ---------------------------------------------------------------------------

printf '=== test 8: plugin mode migrates away from blocks ===\n'
PM_HOME="$TEST_DIR/plugin-mode-home"
PM_WIN="$TEST_DIR/plugin-mode-win"
mkdir -p "$PM_HOME/.claude" "$PM_WIN"
printf 'user notes above\n' > "$PM_HOME/.claude/CLAUDE.md"
run_blocks install "$PM_HOME" "$PM_WIN" > /dev/null
for f in .claude/CLAUDE.md .codex/AGENTS.md .gemini/GEMINI.md AGENTS.md; do
    grep -qF "# >>> $ORG >>>" "$PM_HOME/$f" || fail "setup: home mode should write a block in $f"
done

CLAUDE_BLOCK=remove CODEX_BLOCK=remove CURSOR_BLOCK=remove \
    run_blocks install "$PM_HOME" "$PM_WIN" > "$TEST_DIR/plugin-mode.out"
assert_not_grep "# >>> $ORG >>>" "$PM_HOME/.claude/CLAUDE.md"
assert_grep "user notes above" "$PM_HOME/.claude/CLAUDE.md"
[ ! -e "$PM_HOME/.codex/AGENTS.md" ] \
    || fail "CODEX_BLOCK=remove should delete a file that only held the block"
[ ! -e "$PM_HOME/AGENTS.md" ] \
    || fail "CURSOR_BLOCK=remove should delete a file that only held the block"
grep -qF "# >>> $ORG >>>" "$PM_HOME/.gemini/GEMINI.md" || fail "GEMINI_BLOCK=keep lost its block"

# Idempotent: a second plugin-mode install changes nothing.
CLAUDE_BLOCK=remove CODEX_BLOCK=remove CURSOR_BLOCK=remove \
    run_blocks install "$PM_HOME" "$PM_WIN" > "$TEST_DIR/plugin-mode-2.out"
if grep -qE ' (\+|~|-) ' "$TEST_DIR/plugin-mode-2.out"; then
    fail "second plugin-mode install was not a no-op"
fi

CLAUDE_BLOCK=remove CODEX_BLOCK=remove CURSOR_BLOCK=remove \
    run_blocks status "$PM_HOME" > "$TEST_DIR/plugin-mode-status.out" || true
grep -q "no $ORG block (plugin mode)" "$TEST_DIR/plugin-mode-status.out" \
    || fail "status should report plugin mode for removed blocks"

if CLAUDE_BLOCK=bogus run_blocks install "$PM_HOME" > /dev/null 2>&1; then
    fail "an invalid CLAUDE_BLOCK was accepted"
fi

# Uninstall still removes every block, whatever the modes.
CLAUDE_BLOCK=remove run_blocks uninstall "$PM_HOME" "$PM_WIN" > /dev/null
if [ -f "$PM_HOME/.gemini/GEMINI.md" ] && grep -qF "# >>> $ORG >>>" "$PM_HOME/.gemini/GEMINI.md"; then
    fail "uninstall left a block in .gemini/GEMINI.md"
fi

# ---------------------------------------------------------------------------
# Test 9: the Cursor block carries the Cursor-only rules, others don't
# ---------------------------------------------------------------------------

printf '=== test 9: cursor block appends rule bodies ===\n'
CX_HOME="$TEST_DIR/cursor-extras-home"
mkdir -p "$CX_HOME"
CX_RULE="$TEST_DIR/cursor-rule.mdc"
printf -- '---\ndescription: test rule\nalwaysApply: true\n---\n\n# Cursor-only rule body\n' > "$CX_RULE"
CURSOR_EXTRA_SOURCES_T="$CX_RULE" run_blocks install "$CX_HOME" > /dev/null
assert_grep "Cursor-only rule body" "$CX_HOME/AGENTS.md"
assert_not_grep "alwaysApply: true" "$CX_HOME/AGENTS.md"
assert_not_grep "Cursor-only rule body" "$CX_HOME/.codex/AGENTS.md"
assert_grep "$CANARY_PHRASE" "$CX_HOME/AGENTS.md"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if [ "$FAILED" = "0" ]; then
    printf '\n=== all tests passed ===\n'
    rm -rf "$BUILD_DIR"
    exit 0
fi
printf '\n=== TESTS FAILED ===\n' >&2
exit 1
