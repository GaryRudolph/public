#!/usr/bin/env bash
# Test harness for extensions.sh. Builds sandboxed fake $HOME and $WIN_HOME
# directories, plus a fake SKILLS_SRC / COMMANDS_SRC tree, then exercises
# install / uninstall on both passes — unix-side symlinks AND windows-side
# copies (via a sandboxed WIN_HOME, no actual WSL required).
#
# All assertions are local to the sandbox. The script never touches the real
# $HOME or any other system path.
#
# Required env (set by the calling Makefile):
#   ORG          - "personal" (or any installer identity)
#   AGENTS_DIR   - absolute path to the agents/ dir

set -euo pipefail

: "${ORG:?ORG required}"
: "${AGENTS_DIR:?AGENTS_DIR required}"

EXTENSIONS="$AGENTS_DIR/lib/extensions.sh"
BUILD_DIR="$AGENTS_DIR/build"
TEST_DIR="$BUILD_DIR/test-extensions"
FAKE_HOME="$TEST_DIR/home"
FAKE_WIN_HOME="$TEST_DIR/winhome"
FAKE_SKILLS_SRC="$TEST_DIR/src/skills"
FAKE_COMMANDS_SRC="$TEST_DIR/src/commands"

MARKER=".${ORG}-managed"

FAILED=0
fail() {
    printf 'FAIL: %s\n' "$1" >&2
    FAILED=1
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

rm -rf "$TEST_DIR"
mkdir -p "$FAKE_HOME" "$FAKE_WIN_HOME" "$FAKE_SKILLS_SRC" "$FAKE_COMMANDS_SRC"

# Stage one fake skill and one fake command.
mkdir -p "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
cat > "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md" <<EOF
---
name: ${ORG}-fake-skill
description: Test fixture for the extensions installer.
---

# ${ORG}-fake-skill

Fixture content v1.
EOF

cat > "$FAKE_COMMANDS_SRC/${ORG}-fake-cmd.md" <<EOF
# /${ORG}-fake-cmd

Fixture command content v1.
EOF

# ---------------------------------------------------------------------------
# Helper: run extensions.sh with the sandbox env
# ---------------------------------------------------------------------------

run_ext() {
    local cmd="$1"
    HOME="$FAKE_HOME" \
    ORG="$ORG" \
    AGENTS_DIR="$AGENTS_DIR" \
    SKILLS_SRC="$FAKE_SKILLS_SRC" \
    COMMANDS_SRC="$FAKE_COMMANDS_SRC" \
    CURSOR_SKILLS_HOME="$FAKE_HOME/.cursor/skills" \
    CLAUDE_SKILLS_HOME="$FAKE_HOME/.claude/skills" \
    CLAUDE_COMMANDS_HOME="$FAKE_HOME/.claude/commands" \
    WIN_HOME="$FAKE_WIN_HOME" \
    WIN_CURSOR_SKILLS_HOME="$FAKE_WIN_HOME/.cursor/skills" \
    WIN_CLAUDE_SKILLS_HOME="$FAKE_WIN_HOME/.claude/skills" \
    WIN_CLAUDE_COMMANDS_HOME="$FAKE_WIN_HOME/.claude/commands" \
    bash "$EXTENSIONS" "$cmd"
}

assert_file_exists() {
    [ -f "$1" ] || fail "expected file to exist: $1"
}
assert_file_missing() {
    [ ! -e "$1" ] || fail "expected file to NOT exist: $1"
}
assert_dir_exists() {
    [ -d "$1" ] || fail "expected dir to exist: $1"
}
assert_dir_missing() {
    [ ! -e "$1" ] || fail "expected dir to NOT exist: $1"
}
assert_symlink_to() {
    local link="$1" expected="$2"
    if [ ! -L "$link" ]; then
        fail "expected symlink at $link"
        return
    fi
    local actual
    actual=$(readlink -- "$link")
    [ "$actual" = "$expected" ] || \
        fail "symlink $link points to '$actual', expected '$expected'"
}
assert_files_equal() {
    cmp -s -- "$1" "$2" || fail "files differ: $1 vs $2"
}
assert_files_differ() {
    if cmp -s -- "$1" "$2"; then
        fail "files unexpectedly equal: $1 vs $2"
    fi
}
assert_grep() {
    grep -qF "$1" "$2" 2>/dev/null || fail "expected '$1' in $2"
}

# ---------------------------------------------------------------------------
# Test 1: fresh install creates unix symlinks
# ---------------------------------------------------------------------------

printf '=== test 1: fresh install (unix symlinks) ===\n'
run_ext install > "$TEST_DIR/install.out"

assert_symlink_to "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_symlink_to "$FAKE_HOME/.claude/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_symlink_to "$FAKE_HOME/.claude/commands/${ORG}-fake-cmd.md" \
    "$FAKE_COMMANDS_SRC/${ORG}-fake-cmd.md"

# ---------------------------------------------------------------------------
# Test 2: fresh install creates windows-side copies + markers
# ---------------------------------------------------------------------------

printf '=== test 2: fresh install (windows copies + markers) ===\n'
assert_dir_exists  "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/$MARKER"
assert_grep "Fixture content v1" \
    "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"

assert_dir_exists  "$FAKE_WIN_HOME/.claude/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_WIN_HOME/.claude/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_WIN_HOME/.claude/skills/${ORG}-fake-skill/$MARKER"

assert_file_exists "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md"
assert_file_exists "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md.${MARKER#.}"
assert_grep "Fixture command content v1" \
    "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md"

# Copies are real files, not symlinks
[ ! -L "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill" ] || \
    fail "windows-side skill should be a real dir, not a symlink"
[ ! -L "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md" ] || \
    fail "windows-side command should be a real file, not a symlink"

# ---------------------------------------------------------------------------
# Test 3: idempotent second install (no churn)
# ---------------------------------------------------------------------------

printf '=== test 3: idempotent second install ===\n'
# Capture the windows-side file mtime so we can prove we didn't re-copy.
sleep 1  # ensure mtime resolution will detect any rewrite
WIN_SKILL_BEFORE=$(stat -f '%m' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -c '%Y' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_CMD_BEFORE=$(stat -f '%m' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md" 2>/dev/null \
    || stat -c '%Y' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md")

run_ext install > "$TEST_DIR/install-2.out"

# Expect "no change" output for every line (unix and windows passes alike).
if grep -qE '(\+ |~ )' "$TEST_DIR/install-2.out"; then
    fail "second install was not a no-op; saw changes:"
    grep -E '(\+ |~ )' "$TEST_DIR/install-2.out" >&2 || true
fi

WIN_SKILL_AFTER=$(stat -f '%m' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -c '%Y' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_CMD_AFTER=$(stat -f '%m' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md" 2>/dev/null \
    || stat -c '%Y' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md")

[ "$WIN_SKILL_BEFORE" = "$WIN_SKILL_AFTER" ] || \
    fail "windows-side skill file mtime changed on no-op install"
[ "$WIN_CMD_BEFORE" = "$WIN_CMD_AFTER" ] || \
    fail "windows-side command file mtime changed on no-op install"

# ---------------------------------------------------------------------------
# Test 4: foreign content survives uninstall (preservation property)
# ---------------------------------------------------------------------------

printf '=== test 4: foreign content survives uninstall ===\n'

# Unix-side: an unrelated symlink and a real file the user might have dropped.
mkdir -p "$FAKE_HOME/.cursor/skills"
ln -sf "/some/external/path/external-skill" "$FAKE_HOME/.cursor/skills/external-skill"
mkdir -p "$FAKE_HOME/.claude/skills/hand-rolled-skill"
printf 'hand-rolled\n' > "$FAKE_HOME/.claude/skills/hand-rolled-skill/SKILL.md"
printf 'hand-rolled cmd\n' > "$FAKE_HOME/.claude/commands/hand-rolled.md"

# Windows-side: a directory and a file with NO marker (so we don't own them).
mkdir -p "$FAKE_WIN_HOME/.cursor/skills/foreign-skill"
printf 'foreign content\n' > "$FAKE_WIN_HOME/.cursor/skills/foreign-skill/SKILL.md"
printf 'foreign cmd\n' > "$FAKE_WIN_HOME/.claude/commands/foreign-cmd.md"

# Take snapshots of every foreign artifact so we can prove byte-for-byte equality.
FOREIGN_SNAPSHOT="$TEST_DIR/foreign-snapshot"
mkdir -p "$FOREIGN_SNAPSHOT"
cp -R "$FAKE_HOME/.claude/skills/hand-rolled-skill" "$FOREIGN_SNAPSHOT/hand-rolled-skill"
cp "$FAKE_HOME/.claude/commands/hand-rolled.md" "$FOREIGN_SNAPSHOT/hand-rolled.md"
cp -R "$FAKE_WIN_HOME/.cursor/skills/foreign-skill" "$FOREIGN_SNAPSHOT/foreign-skill"
cp "$FAKE_WIN_HOME/.claude/commands/foreign-cmd.md" "$FOREIGN_SNAPSHOT/foreign-cmd.md"

run_ext uninstall > "$TEST_DIR/uninstall.out"

# Our managed entries should all be gone.
assert_file_missing "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill"
assert_file_missing "$FAKE_HOME/.claude/skills/${ORG}-fake-skill"
assert_file_missing "$FAKE_HOME/.claude/commands/${ORG}-fake-cmd.md"
assert_dir_missing  "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill"
assert_dir_missing  "$FAKE_WIN_HOME/.claude/skills/${ORG}-fake-skill"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md.${MARKER#.}"

# Foreign entries should survive byte-for-byte.
[ -L "$FAKE_HOME/.cursor/skills/external-skill" ] || \
    fail "foreign symlink was removed by uninstall"
assert_dir_exists "$FAKE_HOME/.claude/skills/hand-rolled-skill"
assert_files_equal \
    "$FAKE_HOME/.claude/skills/hand-rolled-skill/SKILL.md" \
    "$FOREIGN_SNAPSHOT/hand-rolled-skill/SKILL.md"
assert_file_exists "$FAKE_HOME/.claude/commands/hand-rolled.md"
assert_files_equal \
    "$FAKE_HOME/.claude/commands/hand-rolled.md" \
    "$FOREIGN_SNAPSHOT/hand-rolled.md"

assert_dir_exists "$FAKE_WIN_HOME/.cursor/skills/foreign-skill"
assert_files_equal \
    "$FAKE_WIN_HOME/.cursor/skills/foreign-skill/SKILL.md" \
    "$FOREIGN_SNAPSHOT/foreign-skill/SKILL.md"
assert_file_exists "$FAKE_WIN_HOME/.claude/commands/foreign-cmd.md"
assert_files_equal \
    "$FAKE_WIN_HOME/.claude/commands/foreign-cmd.md" \
    "$FOREIGN_SNAPSHOT/foreign-cmd.md"

# ---------------------------------------------------------------------------
# Test 5: re-install puts managed entries back without touching foreign ones
# ---------------------------------------------------------------------------

printf '=== test 5: re-install after uninstall ===\n'
run_ext install > "$TEST_DIR/install-3.out"

# Managed entries are back.
assert_symlink_to "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/$MARKER"

# Foreign entries still untouched.
[ -L "$FAKE_HOME/.cursor/skills/external-skill" ] || \
    fail "foreign symlink lost across uninstall/install cycle"
assert_files_equal \
    "$FAKE_WIN_HOME/.cursor/skills/foreign-skill/SKILL.md" \
    "$FOREIGN_SNAPSHOT/foreign-skill/SKILL.md"

# ---------------------------------------------------------------------------
# Test 6: stale windows-side copy refreshes when source changes
# ---------------------------------------------------------------------------

printf '=== test 6: windows-side refresh on source change ===\n'
# Mutate the source skill content.
cat > "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md" <<EOF
---
name: ${ORG}-fake-skill
description: Test fixture for the extensions installer.
---

# ${ORG}-fake-skill

Fixture content v2 (UPDATED).
EOF

run_ext install > "$TEST_DIR/install-4.out"

# Unix symlink: still live, so already reflects v2.
assert_grep "Fixture content v2 (UPDATED)" \
    "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"

# Windows-side copy: must have been refreshed.
assert_grep "Fixture content v2 (UPDATED)" \
    "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
# Output must mention the refresh.
grep -qE "refresh|refreshed" "$TEST_DIR/install-4.out" || \
    fail "expected install output to mention a windows-side refresh"

# Also verify the command refresh path.
printf '# /${ORG}-fake-cmd\n\nFixture command content v2 (UPDATED).\n' \
    > "$FAKE_COMMANDS_SRC/${ORG}-fake-cmd.md"
run_ext install > "$TEST_DIR/install-5.out"
assert_grep "Fixture command content v2 (UPDATED)" \
    "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md"

# ---------------------------------------------------------------------------
# Test 7: orphan cleanup when source deleted
# ---------------------------------------------------------------------------

printf '=== test 7: orphan cleanup ===\n'
# Stage a second source skill, install, then delete it from the source tree.
mkdir -p "$FAKE_SKILLS_SRC/${ORG}-doomed-skill"
cat > "$FAKE_SKILLS_SRC/${ORG}-doomed-skill/SKILL.md" <<EOF
---
name: ${ORG}-doomed-skill
description: Will be deleted to test orphan cleanup.
---
EOF
printf '# /${ORG}-doomed-cmd\n\nDoomed cmd.\n' \
    > "$FAKE_COMMANDS_SRC/${ORG}-doomed-cmd.md"

run_ext install > "$TEST_DIR/install-6.out"
assert_symlink_to "$FAKE_HOME/.cursor/skills/${ORG}-doomed-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-doomed-skill"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-doomed-skill/$MARKER"
assert_file_exists "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md"

# Delete from source.
rm -rf "$FAKE_SKILLS_SRC/${ORG}-doomed-skill"
rm -f  "$FAKE_COMMANDS_SRC/${ORG}-doomed-cmd.md"

run_ext install > "$TEST_DIR/install-7.out"

# Unix-side symlink (broken, points into our SRC) should be cleaned up.
[ ! -L "$FAKE_HOME/.cursor/skills/${ORG}-doomed-skill" ] || \
    fail "orphan unix-side skill symlink survived re-install"
[ ! -L "$FAKE_HOME/.claude/commands/${ORG}-doomed-cmd.md" ] || \
    fail "orphan unix-side command symlink survived re-install"

# Windows-side copies (with markers) should be cleaned up.
assert_dir_missing  "$FAKE_WIN_HOME/.cursor/skills/${ORG}-doomed-skill"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md.${MARKER#.}"

# The surviving managed entries should still be present.
assert_symlink_to "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"

# And so should the foreign entries from earlier.
[ -L "$FAKE_HOME/.cursor/skills/external-skill" ] || \
    fail "foreign symlink lost across orphan cleanup"
assert_dir_exists "$FAKE_WIN_HOME/.cursor/skills/foreign-skill"

# ---------------------------------------------------------------------------
# Test 8: dry-run produces no disk writes
# ---------------------------------------------------------------------------

printf '=== test 8: dry-run is a no-op on disk ===\n'

# Stage another to-be-installed item and confirm dry-run does NOT create it.
mkdir -p "$FAKE_SKILLS_SRC/${ORG}-only-dryrun"
cat > "$FAKE_SKILLS_SRC/${ORG}-only-dryrun/SKILL.md" <<EOF
---
name: ${ORG}-only-dryrun
description: dry.
---
EOF

run_ext dry-run > "$TEST_DIR/dryrun.out"

# Output mentions the would-be creation.
grep -qE "would create.*${ORG}-only-dryrun" "$TEST_DIR/dryrun.out" || \
    fail "dry-run output missing 'would create' for ${ORG}-only-dryrun (unix)"
grep -qE "would copy.*${ORG}-only-dryrun.*win" "$TEST_DIR/dryrun.out" || \
    fail "dry-run output missing 'would copy ... [win]' for ${ORG}-only-dryrun"

# Nothing landed on disk on either side.
[ ! -L "$FAKE_HOME/.cursor/skills/${ORG}-only-dryrun" ] || \
    fail "dry-run created a unix-side symlink"
[ ! -d "$FAKE_WIN_HOME/.cursor/skills/${ORG}-only-dryrun" ] || \
    fail "dry-run created a windows-side directory"

# Clean up.
rm -rf "$FAKE_SKILLS_SRC/${ORG}-only-dryrun"

# ---------------------------------------------------------------------------
# Test 9: status output reflects current state
# ---------------------------------------------------------------------------

printf '=== test 9: status reports ===\n'
run_ext status > "$TEST_DIR/status.out"

# Unix-side line shape: "<pretty-path>   = present (skill)"
grep -qE "${ORG}-fake-skill[[:space:]]+= present" "$TEST_DIR/status.out" || \
    fail "status missing 'present' for ${ORG}-fake-skill (unix)"
# Windows-side line shape: "<pretty-path>   = present (skill) [win]"
grep -qE "${ORG}-fake-skill[[:space:]]+= present.*\[win\]" "$TEST_DIR/status.out" || \
    fail "status missing 'present ... [win]' for ${ORG}-fake-skill"

# ---------------------------------------------------------------------------
# Test 10: WIN_HOME unset → windows pass skipped (macOS / non-WSL Linux)
# ---------------------------------------------------------------------------

printf '=== test 10: WIN_HOME unset skips windows pass ===\n'

# Use a separate sandbox so we can't contaminate the earlier state.
TEST_DIR2="$BUILD_DIR/test-extensions-no-win"
rm -rf "$TEST_DIR2"
mkdir -p "$TEST_DIR2/home"

HOME="$TEST_DIR2/home" \
ORG="$ORG" \
AGENTS_DIR="$AGENTS_DIR" \
SKILLS_SRC="$FAKE_SKILLS_SRC" \
COMMANDS_SRC="$FAKE_COMMANDS_SRC" \
CURSOR_SKILLS_HOME="$TEST_DIR2/home/.cursor/skills" \
CLAUDE_SKILLS_HOME="$TEST_DIR2/home/.claude/skills" \
CLAUDE_COMMANDS_HOME="$TEST_DIR2/home/.claude/commands" \
WIN_HOME="" \
WIN_CURSOR_SKILLS_HOME="" \
WIN_CLAUDE_SKILLS_HOME="" \
WIN_CLAUDE_COMMANDS_HOME="" \
bash "$EXTENSIONS" install > "$TEST_DIR2/install.out"

assert_symlink_to "$TEST_DIR2/home/.cursor/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
# No windows-related output should have been emitted.
if grep -q '\[win\]' "$TEST_DIR2/install.out"; then
    fail "windows pass ran despite empty WIN_HOME"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

if [ "$FAILED" = "0" ]; then
    printf '\nextensions-test: all assertions passed\n'
    exit 0
else
    printf '\nextensions-test: FAILED — see assertions above\n' >&2
    exit 1
fi
