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
#   ORG          - "agerpoint" or "personal"
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
    AGENTS_SKILLS_HOME="$FAKE_HOME/.agents/skills" \
    LEGACY_SKILLS_HOMES="$FAKE_HOME/.gemini/skills:$FAKE_HOME/.codex/skills" \
    CLAUDE_COMMANDS_HOME="$FAKE_HOME/.claude/commands" \
    WIN_HOME="$FAKE_WIN_HOME" \
    WIN_CURSOR_SKILLS_HOME="$FAKE_WIN_HOME/.cursor/skills" \
    WIN_CLAUDE_SKILLS_HOME="$FAKE_WIN_HOME/.claude/skills" \
    WIN_AGENTS_SKILLS_HOME="$FAKE_WIN_HOME/.agents/skills" \
    WIN_LEGACY_SKILLS_HOMES="$FAKE_WIN_HOME/.gemini/skills:$FAKE_WIN_HOME/.codex/skills" \
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

printf '=== test 1: fresh install (Cursor=copy, Claude=symlink) ===\n'
run_ext install > "$TEST_DIR/install.out"

# Cursor skills: real dir + marker (Cursor doesn't follow symlinks).
assert_dir_exists  "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/$MARKER"
assert_grep "Fixture content v1" \
    "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
[ ! -L "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill" ] || \
    fail "unix cursor skill should be a real dir, not a symlink"

# Claude skills + commands: symlinks (Claude follows them).
assert_symlink_to "$FAKE_HOME/.claude/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_symlink_to "$FAKE_HOME/.agents/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_symlink_to "$FAKE_HOME/.claude/commands/${ORG}-fake-cmd.md" \
    "$FAKE_COMMANDS_SRC/${ORG}-fake-cmd.md"
# Commands stay Claude-only: Gemini/Codex must NOT receive the command.
assert_file_missing "$FAKE_HOME/.agents/skills/${ORG}-fake-cmd.md"

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

assert_dir_exists  "$FAKE_WIN_HOME/.agents/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_WIN_HOME/.agents/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_WIN_HOME/.agents/skills/${ORG}-fake-skill/$MARKER"


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
# Capture mtimes on both unix Cursor copy and windows-side copy to prove no re-copy.
sleep 1  # ensure mtime resolution will detect any rewrite
CUR_SKILL_BEFORE=$(stat -c '%Y' "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_SKILL_BEFORE=$(stat -c '%Y' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_CMD_BEFORE=$(stat -c '%Y' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md")

run_ext install > "$TEST_DIR/install-2.out"

# Expect "no change" output for every line (unix and windows passes alike).
if grep -qE '(\+ |~ )' "$TEST_DIR/install-2.out"; then
    fail "second install was not a no-op; saw changes:"
    grep -E '(\+ |~ )' "$TEST_DIR/install-2.out" >&2 || true
fi

CUR_SKILL_AFTER=$(stat -c '%Y' "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_SKILL_AFTER=$(stat -c '%Y' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md")
WIN_CMD_AFTER=$(stat -c '%Y' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md" 2>/dev/null \
    || stat -f '%m' "$FAKE_WIN_HOME/.claude/commands/${ORG}-fake-cmd.md")

[ "$CUR_SKILL_BEFORE" = "$CUR_SKILL_AFTER" ] || \
    fail "unix cursor skill file mtime changed on no-op install"
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
assert_file_missing "$FAKE_HOME/.agents/skills/${ORG}-fake-skill"
assert_file_missing "$FAKE_HOME/.claude/commands/${ORG}-fake-cmd.md"
assert_dir_missing  "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill"
assert_dir_missing  "$FAKE_WIN_HOME/.claude/skills/${ORG}-fake-skill"
assert_dir_missing  "$FAKE_WIN_HOME/.agents/skills/${ORG}-fake-skill"
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
assert_dir_exists  "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/$MARKER"
assert_symlink_to "$FAKE_HOME/.claude/skills/${ORG}-fake-skill" \
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

printf '=== test 6: copy refresh on source change ===\n'
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

# Unix cursor copy: must be refreshed (output content matches source).
assert_grep "Fixture content v2 (UPDATED)" \
    "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"

# Windows-side copy: must have been refreshed too.
assert_grep "Fixture content v2 (UPDATED)" \
    "$FAKE_WIN_HOME/.cursor/skills/${ORG}-fake-skill/SKILL.md"
# Output must mention the refresh.
grep -qE "refresh|refreshed" "$TEST_DIR/install-4.out" || \
    fail "expected install output to mention a refresh"

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
# Cursor skills are copies; Claude commands remain symlinks.
assert_dir_exists  "$FAKE_HOME/.cursor/skills/${ORG}-doomed-skill"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-doomed-skill/$MARKER"
assert_symlink_to  "$FAKE_HOME/.claude/commands/${ORG}-doomed-cmd.md" \
    "$FAKE_COMMANDS_SRC/${ORG}-doomed-cmd.md"
assert_file_exists "$FAKE_WIN_HOME/.cursor/skills/${ORG}-doomed-skill/$MARKER"
assert_file_exists "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md"

# Delete from source.
rm -rf "$FAKE_SKILLS_SRC/${ORG}-doomed-skill"
rm -f  "$FAKE_COMMANDS_SRC/${ORG}-doomed-cmd.md"

run_ext install > "$TEST_DIR/install-7.out"

# Unix cursor copy (marker'd dir) should be cleaned up.
assert_dir_missing "$FAKE_HOME/.cursor/skills/${ORG}-doomed-skill"
# Unix Claude command symlink (broken, points into our SRC) should be cleaned up.
[ ! -L "$FAKE_HOME/.claude/commands/${ORG}-doomed-cmd.md" ] || \
    fail "orphan unix-side command symlink survived re-install"

# Windows-side copies (with markers) should be cleaned up.
assert_dir_missing  "$FAKE_WIN_HOME/.cursor/skills/${ORG}-doomed-skill"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md"
assert_file_missing "$FAKE_WIN_HOME/.claude/commands/${ORG}-doomed-cmd.md.${MARKER#.}"

# The surviving managed entries should still be present.
assert_dir_exists  "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$FAKE_HOME/.cursor/skills/${ORG}-fake-skill/$MARKER"
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

# Output mentions the would-be copies (unix cursor pass and windows pass).
grep -qE "would copy.*${ORG}-only-dryrun" "$TEST_DIR/dryrun.out" || \
    fail "dry-run output missing 'would copy' for ${ORG}-only-dryrun (unix cursor)"
grep -qE "would copy.*${ORG}-only-dryrun.*\[win\]" "$TEST_DIR/dryrun.out" || \
    fail "dry-run output missing 'would copy ... [win]' for ${ORG}-only-dryrun"
# Claude skills: symlink mode, so we see 'would create'.
grep -qE "would create.*${ORG}-only-dryrun" "$TEST_DIR/dryrun.out" || \
    fail "dry-run output missing 'would create' for ${ORG}-only-dryrun (claude)"

# Nothing landed on disk on either side.
[ ! -d "$FAKE_HOME/.cursor/skills/${ORG}-only-dryrun" ] || \
    fail "dry-run created a unix cursor copy"
[ ! -L "$FAKE_HOME/.cursor/skills/${ORG}-only-dryrun" ] || \
    fail "dry-run created a unix cursor symlink"
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
# Test 10: symlink → copy migration
# ---------------------------------------------------------------------------
# Pre-place a legacy symlink in the Cursor skills dir, then run install and
# confirm it is replaced with a real copy + marker.

printf '=== test 10: symlink-to-copy migration for Cursor skills ===\n'

TEST_DIR_MIG="$BUILD_DIR/test-extensions-migration"
rm -rf "$TEST_DIR_MIG"
mkdir -p "$TEST_DIR_MIG/home"

# Pre-create a Cursor skills symlink (simulating a legacy install).
mkdir -p "$TEST_DIR_MIG/home/.cursor/skills"
ln -s "$FAKE_SKILLS_SRC/${ORG}-fake-skill" \
    "$TEST_DIR_MIG/home/.cursor/skills/${ORG}-fake-skill"

HOME="$TEST_DIR_MIG/home" \
ORG="$ORG" \
AGENTS_DIR="$AGENTS_DIR" \
SKILLS_SRC="$FAKE_SKILLS_SRC" \
COMMANDS_SRC="$FAKE_COMMANDS_SRC" \
CURSOR_SKILLS_HOME="$TEST_DIR_MIG/home/.cursor/skills" \
CLAUDE_SKILLS_HOME="$TEST_DIR_MIG/home/.claude/skills" \
CLAUDE_COMMANDS_HOME="$TEST_DIR_MIG/home/.claude/commands" \
WIN_HOME="" \
WIN_CURSOR_SKILLS_HOME="" \
WIN_CLAUDE_SKILLS_HOME="" \
WIN_CLAUDE_COMMANDS_HOME="" \
bash "$EXTENSIONS" install > "$TEST_DIR_MIG/install.out"

# Symlink should be gone; a real copy with marker should be present.
[ ! -L "$TEST_DIR_MIG/home/.cursor/skills/${ORG}-fake-skill" ] || \
    fail "migration: legacy symlink was not replaced"
assert_dir_exists  "$TEST_DIR_MIG/home/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$TEST_DIR_MIG/home/.cursor/skills/${ORG}-fake-skill/SKILL.md"
assert_file_exists "$TEST_DIR_MIG/home/.cursor/skills/${ORG}-fake-skill/$MARKER"
# Claude symlink was created fresh (no prior entry).
assert_symlink_to "$TEST_DIR_MIG/home/.claude/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"

# ---------------------------------------------------------------------------
# Test 11: WIN_HOME unset → windows pass skipped (macOS / non-WSL Linux)
# ---------------------------------------------------------------------------

printf '=== test 11: WIN_HOME unset skips windows pass ===\n'

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
AGENTS_SKILLS_HOME="$TEST_DIR2/home/.agents/skills" \
CLAUDE_COMMANDS_HOME="$TEST_DIR2/home/.claude/commands" \
WIN_HOME="" \
WIN_CURSOR_SKILLS_HOME="" \
WIN_CLAUDE_SKILLS_HOME="" \
WIN_CLAUDE_COMMANDS_HOME="" \
bash "$EXTENSIONS" install > "$TEST_DIR2/install.out"

# Cursor skills: real copy (copy mode is unconditional, not gated on WIN_HOME).
assert_dir_exists  "$TEST_DIR2/home/.cursor/skills/${ORG}-fake-skill"
assert_file_exists "$TEST_DIR2/home/.cursor/skills/${ORG}-fake-skill/$MARKER"
assert_symlink_to "$TEST_DIR2/home/.claude/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
assert_symlink_to "$TEST_DIR2/home/.agents/skills/${ORG}-fake-skill" \
    "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
# No windows-related output should have been emitted.
if grep -q '\[win\]' "$TEST_DIR2/install.out"; then
    fail "windows pass ran despite empty WIN_HOME"
fi

# ---------------------------------------------------------------------------
# Test 12: multi-source, Cursor-only skills, plugin modes, legacy sweep
# ---------------------------------------------------------------------------

printf '=== test 12: multi-source + plugin mode + legacy sweep ===\n'
T3="$BUILD_DIR/test-extensions-modes"
rm -rf "$T3"
H3="$T3/home"; W3="$T3/winhome"
SRC_A="$T3/src/plugin-a/skills"; SRC_B="$T3/src/plugin-b/skills"
SRC_CURSOR="$T3/src/plugin-a/cursor/skills"; CMDS="$T3/src/plugin-a/commands"
LEGACY="$T3/src/legacy-skills"
mkdir -p "$H3" "$W3" "$SRC_A/${ORG}-a" "$SRC_B/${ORG}-b" "$SRC_CURSOR/${ORG}-c" "$CMDS" "$LEGACY/${ORG}-old"
for d in "$SRC_A/${ORG}-a" "$SRC_B/${ORG}-b" "$SRC_CURSOR/${ORG}-c" "$LEGACY/${ORG}-old"; do
    printf -- '---\nname: %s\ndescription: fixture\n---\n' "$(basename "$d")" > "$d/SKILL.md"
done
printf '# cmd\n' > "$CMDS/${ORG}-cmd.md"

# Pre-existing state from the old installer: links into the legacy source in
# the old per-tool dirs, a foreign skill that must survive, and a stray
# marker copy in a retired Windows-side dir.
mkdir -p "$H3/.gemini/skills" "$H3/.codex/skills" "$H3/.claude/skills" "$W3/.gemini/skills/${ORG}-old"
ln -s "$LEGACY/${ORG}-old" "$H3/.gemini/skills/${ORG}-old"
ln -s "$LEGACY/${ORG}-old" "$H3/.claude/skills/${ORG}-old"
ln -s "$SRC_A/${ORG}-a" "$H3/.codex/skills/${ORG}-a"
mkdir -p "$H3/.gemini/skills/someone-elses"
: > "$W3/.gemini/skills/${ORG}-old/$MARKER"

run_ext3() {
    local cmd="$1"; shift
    env HOME="$H3" ORG="$ORG" AGENTS_DIR="$AGENTS_DIR" \
        SKILLS_SRC="$SRC_A:$SRC_B" CURSOR_SKILLS_SRC="$SRC_CURSOR" COMMANDS_SRC="$CMDS" \
        LEGACY_SKILLS_SRC="$LEGACY" \
        WIN_HOME="$W3" "$@" bash "$EXTENSIONS" "$cmd"
}

run_ext3 install > "$T3/install.out"
assert_dir_exists  "$H3/.cursor/skills/${ORG}-a"
assert_dir_exists  "$H3/.cursor/skills/${ORG}-b"
assert_dir_exists  "$H3/.cursor/skills/${ORG}-c"
assert_symlink_to  "$H3/.agents/skills/${ORG}-a" "$SRC_A/${ORG}-a"
assert_symlink_to  "$H3/.agents/skills/${ORG}-b" "$SRC_B/${ORG}-b"
assert_file_missing "$H3/.agents/skills/${ORG}-c"
assert_file_missing "$H3/.claude/skills/${ORG}-c"
assert_symlink_to  "$H3/.claude/skills/${ORG}-b" "$SRC_B/${ORG}-b"
assert_symlink_to  "$H3/.claude/commands/${ORG}-cmd.md" "$CMDS/${ORG}-cmd.md"
[ ! -L "$H3/.gemini/skills/${ORG}-old" ] || fail "legacy link in ~/.gemini/skills survived"
[ ! -L "$H3/.claude/skills/${ORG}-old" ] || fail "legacy link in ~/.claude/skills survived"
[ ! -L "$H3/.codex/skills/${ORG}-a" ] || fail "retired ~/.codex/skills link survived"
assert_dir_exists  "$H3/.gemini/skills/someone-elses"
assert_dir_missing "$W3/.gemini/skills/${ORG}-old"
assert_dir_exists  "$W3/.agents/skills/${ORG}-b"
assert_dir_exists  "$W3/.cursor/skills/${ORG}-c"

# Orphan cleanup must not treat a skill from another source as an orphan.
run_ext3 install > "$T3/install-2.out"
if grep -q "orphan" "$T3/install-2.out"; then
    fail "second multi-source install reported orphans"
fi

# Plugin mode for Cursor and Claude purges their entries, keeps ~/.agents.
run_ext3 install CURSOR_SKILLS_MODE=plugin CLAUDE_SKILLS_MODE=plugin > "$T3/plugin.out"
assert_dir_missing "$H3/.cursor/skills/${ORG}-a"
assert_dir_missing "$H3/.cursor/skills/${ORG}-c"
assert_file_missing "$H3/.claude/skills/${ORG}-a"
assert_file_missing "$H3/.claude/commands/${ORG}-cmd.md"
assert_dir_missing "$W3/.cursor/skills/${ORG}-a"
assert_dir_missing "$W3/.claude/skills/${ORG}-a"
assert_symlink_to  "$H3/.agents/skills/${ORG}-a" "$SRC_A/${ORG}-a"
run_ext3 status CURSOR_SKILLS_MODE=plugin CLAUDE_SKILLS_MODE=plugin > "$T3/plugin-status.out"
assert_grep "plugin mode" "$T3/plugin-status.out"

if run_ext3 install CURSOR_SKILLS_MODE=bogus > /dev/null 2>&1; then
    fail "an invalid CURSOR_SKILLS_MODE was accepted"
fi

# Uninstall clears every destination whatever the modes.
run_ext3 install > /dev/null
run_ext3 uninstall AGENTS_SKILLS_MODE=plugin > "$T3/uninstall.out"
for d in "$H3/.cursor/skills" "$H3/.agents/skills" "$H3/.claude/skills" "$W3/.agents/skills" "$W3/.cursor/skills"; do
    if [ -d "$d" ] && find "$d" -mindepth 1 -maxdepth 1 -name "${ORG}-*" | grep -q .; then
        fail "uninstall left entries in $d"
    fi
done
assert_file_missing "$H3/.claude/commands/${ORG}-cmd.md"
assert_dir_exists  "$H3/.gemini/skills/someone-elses"

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
