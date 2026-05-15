#!/usr/bin/env bash
# Test harness for blocks.sh. Builds a sandboxed fake $HOME and
# fake projects tree, then exercises every install/uninstall path
# (block ops, legacy cleanup, preservation, idempotency, dry-run,
# Windows-host dual pass, and Copilot fan-out for orgs that enable it).
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
#
# Copilot fan-out is exercised when AGENTS_DIR contains a github-copilot/
# template directory (bok only; personal does not have Ticket-to-PR).

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

# Copilot fan-out is enabled only when the source dir exists.
COPILOT_SRC_DIR=""
if [ -d "$AGENTS_DIR/github-copilot" ] && \
   [ -f "$AGENTS_DIR/github-copilot/copilot-instructions.md" ] && \
   [ -f "$AGENTS_DIR/github-copilot/copilot-setup-steps.yml" ]; then
    # Stage a copy in the sandbox so the test can mutate it without touching
    # the real BOK source tree.
    COPILOT_SRC_DIR="$TEST_DIR/copilot-src"
    mkdir -p "$COPILOT_SRC_DIR"
    cp "$AGENTS_DIR/github-copilot/copilot-instructions.md" "$COPILOT_SRC_DIR/"
    cp "$AGENTS_DIR/github-copilot/copilot-setup-steps.yml" "$COPILOT_SRC_DIR/"
fi

# fan-out repos: extra siblings used only when COPILOT_SRC_DIR is set.
# Each will receive both Copilot files via the fan-out logic.
REPO_FANOUT_A=""
REPO_FANOUT_B=""
if [ -n "$COPILOT_SRC_DIR" ]; then
    REPO_FANOUT_A=$(mk_repo "fanout-a")
    REPO_FANOUT_B=$(mk_repo "fanout-b")
    # Plant a stale copy in REPO_FANOUT_B so we can test update-on-change.
    mkdir -p "$REPO_FANOUT_B/.github/workflows"
    printf 'stale instructions from before\n' \
        > "$REPO_FANOUT_B/.github/copilot-instructions.md"
    printf 'name: stale setup\n' \
        > "$REPO_FANOUT_B/.github/workflows/copilot-setup-steps.yml"
fi

# A fake bok-self repo: should always be skipped during the Copilot fan-out
# because $REPO_ROOT names it.
REPO_BOK_SELF=$(mk_repo "bok-self")
FAKE_REPO_ROOT="$REPO_BOK_SELF"

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
    REPO_ROOT="$FAKE_REPO_ROOT" \
    COPILOT_SRC="$COPILOT_SRC_DIR" \
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

# @-import in Claude/Gemini/Cursor; canary inlined in Codex.
assert_grep "@" "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "AGENTS.md" "$FAKE_HOME/.claude/CLAUDE.md"
assert_grep "@" "$FAKE_HOME/.gemini/GEMINI.md"
assert_grep "$CANARY_PHRASE" "$FAKE_HOME/.codex/AGENTS.md"
assert_grep "@" "$FAKE_HOME/AGENTS.md"

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

# Copilot fan-out should NOT produce a CONFLICTS section any more.
if grep -q "CONFLICTS" "$TEST_DIR/install.out"; then
    fail "install output should not contain CONFLICTS (Copilot files are BOK-managed, not v1)"
fi

# Copilot fan-out behavior (only when source templates are available).
if [ -n "$COPILOT_SRC_DIR" ]; then
    # Both files installed into a previously-empty repo.
    assert_file_exists "$REPO_FANOUT_A/.github/copilot-instructions.md"
    assert_file_exists "$REPO_FANOUT_A/.github/workflows/copilot-setup-steps.yml"
    cmp -s "$COPILOT_SRC_DIR/copilot-instructions.md" \
           "$REPO_FANOUT_A/.github/copilot-instructions.md" \
        || fail "fanout-a copilot-instructions.md content differs from source"
    cmp -s "$COPILOT_SRC_DIR/copilot-setup-steps.yml" \
           "$REPO_FANOUT_A/.github/workflows/copilot-setup-steps.yml" \
        || fail "fanout-a copilot-setup-steps.yml content differs from source"

    # A repo that had stale content gets updated to match source.
    cmp -s "$COPILOT_SRC_DIR/copilot-instructions.md" \
           "$REPO_FANOUT_B/.github/copilot-instructions.md" \
        || fail "fanout-b: stale copilot-instructions.md was not updated"
    cmp -s "$COPILOT_SRC_DIR/copilot-setup-steps.yml" \
           "$REPO_FANOUT_B/.github/workflows/copilot-setup-steps.yml" \
        || fail "fanout-b: stale copilot-setup-steps.yml was not updated"

    # The bok-self repo must be skipped.
    [ ! -f "$REPO_BOK_SELF/.github/copilot-instructions.md" ] \
        || fail "bok-self: copilot files should NOT have been written (bok skips itself)"

    # The installer should print a copilot summary line.
    grep -q "^copilot:" "$TEST_DIR/install.out" \
        || fail "expected 'copilot:' summary line in install output"
fi

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
# The home side must still use @-imports (unchanged from test 1).
assert_grep "@" "$FAKE_HOME/.claude/CLAUDE.md"
assert_not_grep "$CANARY_PHRASE" "$FAKE_HOME/.claude/CLAUDE.md"

# ---------------------------------------------------------------------------
# Test 5b: Copilot fan-out idempotency + change-propagation
# ---------------------------------------------------------------------------

if [ -n "$COPILOT_SRC_DIR" ]; then
    printf '=== test 5b: copilot fan-out idempotency ===\n'

    # Snapshot the fan-out target files; a clean re-run should not touch them.
    pre_a=$(stat -f '%m %z' "$REPO_FANOUT_A/.github/copilot-instructions.md" 2>/dev/null \
            || stat -c '%Y %s' "$REPO_FANOUT_A/.github/copilot-instructions.md")
    run_blocks install > "$TEST_DIR/install_fanout_idem.out"
    sed 's/^/  /' "$TEST_DIR/install_fanout_idem.out"
    post_a=$(stat -f '%m %z' "$REPO_FANOUT_A/.github/copilot-instructions.md" 2>/dev/null \
             || stat -c '%Y %s' "$REPO_FANOUT_A/.github/copilot-instructions.md")
    [ "$pre_a" = "$post_a" ] \
        || fail "fanout-a: idempotent re-install should NOT modify copilot-instructions.md (was $pre_a, now $post_a)"

    grep -qE "= [0-9]+ unchanged" "$TEST_DIR/install_fanout_idem.out" \
        || fail "expected copilot summary to report 'unchanged' on idempotent re-run"

    printf '=== test 5c: copilot fan-out change propagation ===\n'

    # Mutate the source template; next install should overwrite both repos.
    printf '\n## Updated template line\n' >> "$COPILOT_SRC_DIR/copilot-instructions.md"
    run_blocks install > "$TEST_DIR/install_fanout_update.out"
    sed 's/^/  /' "$TEST_DIR/install_fanout_update.out"

    assert_grep "Updated template line" \
        "$REPO_FANOUT_A/.github/copilot-instructions.md"
    assert_grep "Updated template line" \
        "$REPO_FANOUT_B/.github/copilot-instructions.md"
    grep -qE "~ [0-9]+ updated" "$TEST_DIR/install_fanout_update.out" \
        || fail "expected copilot summary to report 'updated' after source change"
fi

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

# Copilot files should be removed from every sibling repo (but not bok-self).
if [ -n "$COPILOT_SRC_DIR" ]; then
    assert_file_missing "$REPO_FANOUT_A/.github/copilot-instructions.md"
    assert_file_missing "$REPO_FANOUT_A/.github/workflows/copilot-setup-steps.yml"
    assert_file_missing "$REPO_FANOUT_B/.github/copilot-instructions.md"
    assert_file_missing "$REPO_FANOUT_B/.github/workflows/copilot-setup-steps.yml"
    # bok-self never had them; should still not.
    [ ! -f "$REPO_BOK_SELF/.github/copilot-instructions.md" ] \
        || fail "bok-self: should remain free of copilot files after uninstall"
fi

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
# Summary
# ---------------------------------------------------------------------------

if [ "$FAILED" = "0" ]; then
    printf '\n=== all tests passed ===\n'
    rm -rf "$BUILD_DIR"
    exit 0
fi
printf '\n=== TESTS FAILED ===\n' >&2
exit 1
