#!/usr/bin/env bash
# Test harness for hooks.sh. Builds a sandboxed fake $HOME and exercises
# install / uninstall / wrapper behavior. Never touches the real $HOME.
#
# Required env (set by the calling Makefile):
#   ORG          - "agerpoint" or "personal"
#   AGENTS_DIR   - absolute path to the agents/ dir

set -euo pipefail

: "${ORG:?ORG required}"
: "${AGENTS_DIR:?AGENTS_DIR required}"

HOOKS="$AGENTS_DIR/lib/hooks.sh"
EXTENSIONS="$AGENTS_DIR/lib/extensions.sh"
BUILD_DIR="$AGENTS_DIR/build"
TEST_DIR="$BUILD_DIR/test-hooks"
FAKE_HOME="$TEST_DIR/home"
FAKE_SKILLS_SRC="$TEST_DIR/src/skills"
FAKE_COMMANDS_SRC="$TEST_DIR/src/commands"
FAKE_DENY_SRC="$TEST_DIR/src/enforce-denylist.sh"
FAKE_CURSOR="$FAKE_HOME/.cursor"
HOOK_SCRIPT="$FAKE_CURSOR/hooks/${ORG}-refresh-skills.sh"
HOOKS_JSON="$FAKE_CURSOR/hooks.json"
HOOKS_MARKER="$FAKE_CURSOR/hooks.json.${ORG}-managed"
DENY_SCRIPT="$FAKE_CURSOR/hooks/${ORG}-enforce-denylist.sh"
CURSOR_SKILLS="$FAKE_CURSOR/skills"
MARKER=".${ORG}-managed"

FAILED=0
fail() {
    printf 'FAIL: %s\n' "$1" >&2
    FAILED=1
}

rm -rf "$TEST_DIR"
mkdir -p "$FAKE_HOME" "$FAKE_SKILLS_SRC" "$FAKE_COMMANDS_SRC" "$CURSOR_SKILLS"

mkdir -p "$FAKE_SKILLS_SRC/${ORG}-fake-skill"
cat > "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md" <<EOF
---
name: ${ORG}-fake-skill
description: Test fixture for the hooks installer.
---

# ${ORG}-fake-skill

Fixture content v1.
EOF

printf '#!/bin/bash\nprintf "{\\"permission\\":\\"allow\\"}\\n"\n' > "$FAKE_DENY_SRC"

cat > "$FAKE_COMMANDS_SRC/${ORG}-fake-cmd.md" <<EOF
# /${ORG}-fake-cmd

Fixture command content v1.
EOF

run_hooks() {
    local cmd="$1"; shift
    env "$@" \
    HOME="$FAKE_HOME" \
    ORG="$ORG" \
    AGENTS_DIR="$AGENTS_DIR" \
    SKILLS_SRC="$FAKE_SKILLS_SRC" \
    COMMANDS_SRC="$FAKE_COMMANDS_SRC" \
    CURSOR_DATA_HOME="$FAKE_CURSOR" \
    PLUGINS_DIR="$TEST_DIR/src" \
    DENYLIST_HOOK_SRC="$FAKE_DENY_SRC" \
    PATH="/nonexistent:$PATH" \
    bash "$HOOKS" "$cmd"
}

run_ext_install() {
    HOME="$FAKE_HOME" \
    ORG="$ORG" \
    AGENTS_DIR="$AGENTS_DIR" \
    SKILLS_SRC="$FAKE_SKILLS_SRC" \
    COMMANDS_SRC="$FAKE_COMMANDS_SRC" \
    CURSOR_SKILLS_HOME="$CURSOR_SKILLS" \
    CLAUDE_SKILLS_HOME="$FAKE_HOME/.claude/skills" \
    CLAUDE_COMMANDS_HOME="$FAKE_HOME/.claude/commands" \
    WIN_HOME="" \
    bash "$EXTENSIONS" install
}

assert_file_exists() {
    [ -f "$1" ] || fail "expected file to exist: $1"
}
assert_file_missing() {
    [ ! -e "$1" ] || fail "expected file to NOT exist: $1"
}
assert_executable() {
    [ -x "$1" ] || fail "expected executable: $1"
}
assert_grep() {
    grep -qF "$1" "$2" 2>/dev/null || fail "expected '$1' in $2"
}
assert_not_grep() {
    if grep -qF "$1" "$2" 2>/dev/null; then
        fail "did not expect '$1' in $2"
    fi
}

# ---------------------------------------------------------------------------
# Test 1: fresh install writes hook script + hooks.json
# ---------------------------------------------------------------------------

printf 'T01: fresh install\n'
run_hooks install
assert_executable "$HOOK_SCRIPT"
assert_file_exists "$HOOKS_JSON"
assert_file_exists "$HOOKS_MARKER"
assert_grep "${ORG}-refresh-skills" "$HOOKS_JSON"
assert_grep 'sessionStart' "$HOOKS_JSON"
assert_grep 'afterFileEdit' "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Test 2: idempotent re-install (no duplicate entries)
# ---------------------------------------------------------------------------

printf 'T02: idempotent re-install\n'
run_hooks install
count=$(grep -c "${ORG}-refresh-skills" "$HOOKS_JSON" || true)
[ "$count" -eq 2 ] || fail "expected 2 hook entries, got $count"

# ---------------------------------------------------------------------------
# Test 3: merge preserves foreign hook
# ---------------------------------------------------------------------------

printf 'T03: merge preserves foreign hook\n'
rm -rf "$FAKE_CURSOR"
mkdir -p "$FAKE_CURSOR"
cat > "$HOOKS_JSON" <<'EOF'
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "./hooks/foreign-hook.sh"
      }
    ]
  }
}
EOF

run_hooks install
assert_grep 'foreign-hook.sh' "$HOOKS_JSON"
assert_grep "${ORG}-refresh-skills" "$HOOKS_JSON"
assert_file_missing "$HOOKS_MARKER"

# ---------------------------------------------------------------------------
# Test 4: uninstall removes our entries but keeps foreign hook
# ---------------------------------------------------------------------------

printf 'T04: uninstall keeps foreign hook\n'
run_hooks uninstall || fail "uninstall failed"
assert_file_missing "$HOOK_SCRIPT"
assert_grep 'foreign-hook.sh' "$HOOKS_JSON"
assert_not_grep "${ORG}-refresh-skills" "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Test 5: uninstall removes hooks.json we created
# ---------------------------------------------------------------------------

printf 'T05: uninstall removes created hooks.json\n'
rm -rf "$FAKE_CURSOR"
mkdir -p "$FAKE_CURSOR"
run_hooks install
run_hooks uninstall
assert_file_missing "$HOOKS_JSON"
assert_file_missing "$HOOKS_MARKER"

# ---------------------------------------------------------------------------
# Test 6: wrapper skips non-skill payloads
# ---------------------------------------------------------------------------

printf 'T06: wrapper skips non-skill payloads\n'
run_ext_install
run_hooks install
LOG="$FAKE_CURSOR/${ORG}-refresh.log"
rm -f "$LOG"
printf '{"hook_event_name":"afterFileEdit","file_path":"/tmp/unrelated.txt"}' | HOME="$FAKE_HOME" bash "$HOOK_SCRIPT"
[ ! -f "$LOG" ] && pass_skip=1 || {
    [ ! -s "$LOG" ] || fail "log should be empty for non-skill payload"
}

# ---------------------------------------------------------------------------
# Test 7: wrapper refreshes copy when skill payload matches
# ---------------------------------------------------------------------------

printf 'T07: wrapper refreshes on skill edit payload\n'
dest="$CURSOR_SKILLS/${ORG}-fake-skill"
assert_file_exists "$dest/SKILL.md"
printf 'stale' > "$dest/SKILL.md"
payload=$(printf '{"hook_event_name":"afterFileEdit","file_path":"%s"}' "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md")
printf '%s' "$payload" | HOME="$FAKE_HOME" bash "$HOOK_SCRIPT"
cmp -s -- "$dest/SKILL.md" "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md" \
    || fail "wrapper did not refresh stale skill copy"

# ---------------------------------------------------------------------------
# Test 8: sessionStart (empty payload) triggers refresh
# ---------------------------------------------------------------------------

printf 'T08: sessionStart triggers refresh\n'
printf 'stale again' > "$dest/SKILL.md"
printf '{"hook_event_name":"sessionStart","conversation_id":"x"}' | HOME="$FAKE_HOME" bash "$HOOK_SCRIPT"
cmp -s -- "$dest/SKILL.md" "$FAKE_SKILLS_SRC/${ORG}-fake-skill/SKILL.md" \
    || fail "sessionStart did not refresh stale skill copy"

# ---------------------------------------------------------------------------
# Test 9: install works with jq masked off PATH
# ---------------------------------------------------------------------------

printf 'T09: no jq dependency\n'
rm -rf "$FAKE_CURSOR"
mkdir -p "$FAKE_CURSOR"
run_hooks install
assert_executable "$HOOK_SCRIPT"
assert_file_exists "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Test 10: denylist hook is copied and registered failClosed
# ---------------------------------------------------------------------------

printf 'T10: denylist hook\n'
[ -f "$DENY_SCRIPT" ] && [ ! -L "$DENY_SCRIPT" ] || fail "denylist hook should be a real copy"
cmp -s "$FAKE_DENY_SRC" "$DENY_SCRIPT" || fail "denylist hook differs from source"
python3 - "$HOOKS_JSON" "$ORG" <<'PY' || fail "denylist entries missing or not failClosed"
import json, sys
hooks = json.load(open(sys.argv[1]))["hooks"]
cmd = "./hooks/" + sys.argv[2] + "-enforce-denylist.sh"
assert any(h["command"] == cmd and h.get("failClosed") for h in hooks["beforeShellExecution"])
assert any(h["command"] == cmd for h in hooks["preToolUse"])
PY

# ---------------------------------------------------------------------------
# Test 11: a foreign entry added after we created hooks.json survives
# ---------------------------------------------------------------------------

printf 'T11: re-install keeps later foreign entries\n'
assert_file_exists "$HOOKS_MARKER"
python3 - "$HOOKS_JSON" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d["hooks"].setdefault("stop", []).append({"command": "./hooks/mine.sh"})
json.dump(d, open(p, "w"), indent=2)
PY
run_hooks install
assert_grep 'mine.sh' "$HOOKS_JSON"
run_hooks uninstall
assert_file_exists "$HOOKS_JSON"
assert_grep 'mine.sh' "$HOOKS_JSON"
assert_not_grep "${ORG}-" "$HOOKS_JSON"
assert_file_missing "$DENY_SCRIPT"

# ---------------------------------------------------------------------------
# Test 12: plugin mode drops the refresh hook, keeps the denylist
# ---------------------------------------------------------------------------

printf 'T12: cursor plugin mode\n'
rm -rf "$FAKE_CURSOR"; mkdir -p "$FAKE_CURSOR"
run_hooks install
assert_executable "$HOOK_SCRIPT"
run_hooks install CURSOR_SKILLS_MODE=plugin
assert_file_missing "$HOOK_SCRIPT"
assert_not_grep "${ORG}-refresh-skills" "$HOOKS_JSON"
assert_grep "${ORG}-enforce-denylist" "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Test 13: a hand-installed denylist hook from the old README is adopted
# ---------------------------------------------------------------------------

printf 'T13: adopt hand-installed denylist hook\n'
rm -rf "$FAKE_CURSOR"; mkdir -p "$FAKE_CURSOR/hooks"
ln -s "$AGENTS_DIR/cursor/hooks/enforce-denylist.sh" "$FAKE_CURSOR/hooks/enforce-denylist.sh"
cat > "$HOOKS_JSON" <<'EOF'
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      { "command": "./hooks/enforce-denylist.sh", "failClosed": true }
    ]
  }
}
EOF
run_hooks install
[ ! -L "$FAKE_CURSOR/hooks/enforce-denylist.sh" ] || fail "hand-installed link should be replaced"
assert_not_grep '"./hooks/enforce-denylist.sh"' "$HOOKS_JSON"
assert_grep "${ORG}-enforce-denylist" "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Test 14: uninstall removes the refresh log and lock
# ---------------------------------------------------------------------------

printf 'T14: uninstall cleans refresh log and lock\n'
: > "$FAKE_CURSOR/${ORG}-refresh.log"
: > "$FAKE_CURSOR/.${ORG}-refresh.lock"
run_hooks uninstall
assert_file_missing "$FAKE_CURSOR/${ORG}-refresh.log"
assert_file_missing "$FAKE_CURSOR/.${ORG}-refresh.lock"
# That hooks.json predates us (T13), so it stays, minus our entries.
assert_not_grep "${ORG}-" "$HOOKS_JSON"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if [ "$FAILED" -eq 0 ]; then
    printf 'hooks-test.sh: all tests passed\n'
else
    printf 'hooks-test.sh: FAILURES\n' >&2
    exit 1
fi
