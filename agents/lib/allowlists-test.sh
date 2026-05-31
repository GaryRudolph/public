#!/usr/bin/env bash
# Test harness for allowlists.sh. Builds sandboxed fake home directories and
# a fake meta-source JSON, then exercises every subcommand and edge case:
# first-install (with and without prior file), idempotence, rotation across
# gaps, unbounded growth, user-edit auto-promotion, two-installer coexistence,
# uninstall semantics, diff/restore round-trip, clean, foreign-file detection,
# flock serialization, CLI passthrough, Claude format translation, and Windows
# dual-pass (via a sandboxed WIN_HOME — no real WSL required).
#
# All assertions are local to the sandbox. Never touches the real $HOME.
#
# Required env (set by the calling Makefile):
#   ORG        - "agerpoint" or "personal"
#   AGENTS_DIR - absolute path to the agents/ dir

set -euo pipefail

: "${ORG:?ORG required}"
: "${AGENTS_DIR:?AGENTS_DIR required}"

command -v jq >/dev/null 2>&1 || {
    printf 'skip: jq not found; allowlists-test.sh requires jq\n' >&2
    exit 0
}

ALLOWLISTS="$AGENTS_DIR/lib/allowlists.sh"
BUILD_DIR="$AGENTS_DIR/build"
TEST_DIR="$BUILD_DIR/test-allowlists"

FAILED=0
fail() { printf 'FAIL: %s\n' "$1" >&2; FAILED=$((FAILED + 1)); }

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR/meta" "$TEST_DIR/homes"

# Minimal but representative meta-source that exercises all three schema kinds.
META="$TEST_DIR/meta/meta.json"
cat > "$META" <<'ENDJSON'
{
  "shell":    { "allow": ["git status", "make test"], "deny": ["rm -rf /"] },
  "mcp":      { "allow": ["notion:*", "slack:*"],     "deny": [] },
  "read":     { "deny": [] },
  "write":    { "deny": [] },
  "webfetch": { "allow": ["*.github.com", "docs.python.org"], "deny": [] }
}
ENDJSON

# A second meta-source with different entries (used for coexistence tests).
META2="$TEST_DIR/meta/meta2.json"
cat > "$META2" <<'ENDJSON'
{
  "shell":    { "allow": ["pytest", "npm test"],  "deny": [] },
  "mcp":      { "allow": ["miro-mcp:*"],           "deny": [] },
  "read":     { "deny": [] },
  "write":    { "deny": [] },
  "webfetch": { "allow": ["*.npmjs.com"],           "deny": [] }
}
ENDJSON

# Create a fresh home-like directory with .cursor/ and .claude/ subdirs.
mk_home() {
    local d="$TEST_DIR/homes/$1"
    mkdir -p "$d/.cursor" "$d/.claude"
    printf '%s' "$d"
}

# Run allowlists.sh with a sandboxed home. REMOVE_HISTORY defaults to "no" so
# the uninstall prompt never blocks the suite on a TTY; a caller can export
# REMOVE_HISTORY=yes to exercise the removal path.
run_al() {
    local home="$1" meta="$2"; shift 2
    ORG="$ORG" \
    ALLOWLISTS_SRC="$meta" \
    CURSOR_DATA_HOME="$home/.cursor" \
    CLAUDE_DATA_HOME="$home/.claude" \
    REMOVE_HISTORY="${REMOVE_HISTORY:-no}" \
    bash "$ALLOWLISTS" "$@"
}

# Run with a specific ORG override (for coexistence tests).
run_al_org() {
    local org_val="$1" home="$2" meta="$3"; shift 3
    ORG="$org_val" \
    ALLOWLISTS_SRC="$meta" \
    CURSOR_DATA_HOME="$home/.cursor" \
    CLAUDE_DATA_HOME="$home/.claude" \
    REMOVE_HISTORY="${REMOVE_HISTORY:-no}" \
    bash "$ALLOWLISTS" "$@"
}

# Run with an explicit sandboxed WIN_HOME so the Windows dual pass fires
# without any real WSL check (init_win_home short-circuits when WIN_HOME
# is already set, so wsl/cmd.exe are never invoked).
run_al_win() {
    local home="$1" win_home="$2" meta="$3"; shift 3
    ORG="$ORG" \
    ALLOWLISTS_SRC="$meta" \
    CURSOR_DATA_HOME="$home/.cursor" \
    CLAUDE_DATA_HOME="$home/.claude" \
    WIN_HOME="$win_home" \
    WIN_CURSOR_DATA_HOME="$win_home/.cursor" \
    WIN_CLAUDE_DATA_HOME="$win_home/.claude" \
    REMOVE_HISTORY="${REMOVE_HISTORY:-no}" \
    bash "$ALLOWLISTS" "$@"
}

# Count .N backup files for a stem+parent combination.
count_hist() {
    local stem="$1" parent="$2"
    find "$parent/.history" -maxdepth 1 -name "${stem}.json.[0-9]*" -type f 2>/dev/null \
        | wc -l | tr -d ' '
}

# ---------------------------------------------------------------------------
# T01: First-install, no prior file → targets created, no .history/ created
# ---------------------------------------------------------------------------
printf '[T01] first-install, no prior file\n'
H=$(mk_home t01)
run_al "$H" "$META" install >/dev/null

[ -f "$H/.cursor/permissions.json" ] || fail "T01: permissions.json not created"
[ -f "$H/.cursor/cli-config.json"  ] || fail "T01: cli-config.json not created"
[ -f "$H/.claude/settings.json"    ] || fail "T01: settings.json not created"
[ ! -d "$H/.cursor/.history"       ] || fail "T01: .cursor/.history/ must not be created on first install"
[ ! -d "$H/.claude/.history"       ] || fail "T01: .claude/.history/ must not be created on first install"
# Rendered files must be valid JSON.
jq . "$H/.cursor/permissions.json" >/dev/null 2>&1 || fail "T01: permissions.json invalid JSON"
jq . "$H/.cursor/cli-config.json"  >/dev/null 2>&1 || fail "T01: cli-config.json invalid JSON"
jq . "$H/.claude/settings.json"    >/dev/null 2>&1 || fail "T01: settings.json invalid JSON"

# ---------------------------------------------------------------------------
# T02: Idempotence — second install is a no-op (no new .history entries)
# ---------------------------------------------------------------------------
printf '[T02] idempotence\n'
snap_p=$(cat "$H/.cursor/permissions.json")
snap_c=$(cat "$H/.cursor/cli-config.json")
snap_s=$(cat "$H/.claude/settings.json")
run_al "$H" "$META" install >/dev/null
[ "$(cat "$H/.cursor/permissions.json")" = "$snap_p" ] || fail "T02: permissions.json changed"
[ "$(cat "$H/.cursor/cli-config.json")"  = "$snap_c" ] || fail "T02: cli-config.json changed"
[ "$(cat "$H/.claude/settings.json")"    = "$snap_s" ] || fail "T02: settings.json changed"
[ ! -d "$H/.cursor/.history"             ] || fail "T02: .history/ created by idempotent install"

# ---------------------------------------------------------------------------
# T03: First-install with prior file → backup in .history/
# ---------------------------------------------------------------------------
printf '[T03] first-install with prior file\n'
H3=$(mk_home t03)
# Pre-seed a live file that was NOT written by us (no sidecar exists yet).
printf '{"terminalAllowlist":["prior-entry"]}\n' > "$H3/.cursor/permissions.json"
run_al "$H3" "$META" install >/dev/null

[ -d "$H3/.cursor/.history"                           ] || fail "T03: .cursor/.history/ not created"
[ -f "$H3/.cursor/.history/permissions.json.1"        ] || fail "T03: backup .1 not created"
old=$(jq -r '.terminalAllowlist[0]' "$H3/.cursor/.history/permissions.json.1")
[ "$old" = "prior-entry"                              ] || fail "T03: backup does not contain old content (got: $old)"
# settings.json had no prior file → no claude .history/ yet.
[ ! -d "$H3/.claude/.history"                         ] || fail "T03: claude .history/ created without prior file"

# ---------------------------------------------------------------------------
# T04: First-install conflict guardrail — abort when .history/.1 exists with
#      no agerpoint sidecar (paranoia: some other tool managed this file).
# ---------------------------------------------------------------------------
printf '[T04] first-install conflict guardrail\n'
H4=$(mk_home t04)
mkdir -p "$H4/.cursor/.history"
printf '{"terminalAllowlist":["foreign-entry"]}\n' \
    > "$H4/.cursor/.history/permissions.json.1"
# No agerpoint sidecar → installer should refuse and exit non-zero.
rc=0
run_al "$H4" "$META" install >/dev/null 2>/dev/null || rc=$?
[ "$rc" -ne 0 ] || fail "T04: install should have aborted (got exit 0)"
[ ! -f "$H4/.cursor/permissions.json" ] || fail "T04: permissions.json must not be written after abort"

# ---------------------------------------------------------------------------
# T05: .N rotation across gaps — deleting an intermediate backup doesn't
#      prevent subsequent rotations from running correctly.
# ---------------------------------------------------------------------------
printf '[T05] .N rotation across gaps\n'
H5=$(mk_home t05)

# Build four versioned meta files so each install produces a different render.
for v in 1 2 3 4 5; do
    f="$TEST_DIR/meta/v${v}.json"
    entries=""
    for i in $(seq 1 "$v"); do entries="${entries}\"cmd-$i\","; done
    entries="${entries%,}"
    printf '{"shell":{"allow":[%s],"deny":[]},"mcp":{"allow":[],"deny":[]},"read":{"deny":[]},"write":{"deny":[]},"webfetch":{"allow":[],"deny":[]}}\n' \
        "$entries" > "$f"
done

# Install v1 (no prior file → no backup).
run_al "$H5" "$TEST_DIR/meta/v1.json" install >/dev/null
[ ! -d "$H5/.cursor/.history" ] || fail "T05: .history/ should not exist after v1 install"

# Install v2 → rotates live(v1) into .1.
run_al "$H5" "$TEST_DIR/meta/v2.json" install >/dev/null
[ "$(count_hist permissions "$H5/.cursor")" = "1" ] || fail "T05: expected 1 backup after v2"

# Install v3 → .1=v2, .2=v1.
run_al "$H5" "$TEST_DIR/meta/v3.json" install >/dev/null
[ "$(count_hist permissions "$H5/.cursor")" = "2" ] || fail "T05: expected 2 backups after v3"

# Install v4 → .1=v3, .2=v2, .3=v1.
run_al "$H5" "$TEST_DIR/meta/v4.json" install >/dev/null
[ "$(count_hist permissions "$H5/.cursor")" = "3" ] || fail "T05: expected 3 backups after v4"

# Delete .2 to create a gap (.1 and .3 remain).
rm "$H5/.cursor/.history/permissions.json.2"

# Install v5 → max is now 3, so: .3→.4, skip .2 (gone), .1→.2, live→.1.
run_al "$H5" "$TEST_DIR/meta/v5.json" install >/dev/null
[ -f "$H5/.cursor/.history/permissions.json.1" ] || fail "T05: .1 missing after gap install"
[ -f "$H5/.cursor/.history/permissions.json.2" ] || fail "T05: .2 missing after gap install"
[ -f "$H5/.cursor/.history/permissions.json.4" ] || fail "T05: .4 missing after gap install (was .3)"
[ ! -f "$H5/.cursor/.history/permissions.json.3" ] || fail "T05: .3 should be absent (gap preserved)"

# ---------------------------------------------------------------------------
# T06: Unbounded growth — 5 renders, no cap
# ---------------------------------------------------------------------------
printf '[T06] unbounded growth\n'
H6=$(mk_home t06)

for v in 1 2 3 4 5 6; do
    f="$TEST_DIR/meta/grow${v}.json"
    printf '{"shell":{"allow":["grow-%s"],"deny":[]},"mcp":{"allow":[],"deny":[]},"read":{"deny":[]},"write":{"deny":[]},"webfetch":{"allow":[],"deny":[]}}\n' \
        "$v" > "$f"
    run_al "$H6" "$f" install >/dev/null
done

n=$(count_hist permissions "$H6/.cursor")
[ "$n" = "5" ] || fail "T06: expected 5 backups after 6 installs (got $n)"

# ---------------------------------------------------------------------------
# T07: Manual-edit auto-promotion — engineer adds an entry directly to the
#      live file; next render captures it in the user-managed sidecar.
# ---------------------------------------------------------------------------
printf '[T07] manual-edit auto-promotion\n'
H7=$(mk_home t07)
run_al "$H7" "$META" install >/dev/null

# Add an entry to the live permissions.json by hand.
tmp="$H7/.cursor/permissions.json.tmp"
jq '.terminalAllowlist += ["user-added-cmd"]' "$H7/.cursor/permissions.json" > "$tmp"
mv "$tmp" "$H7/.cursor/permissions.json"

# Re-render — should detect the extra entry and save it to user-managed sidecar.
run_al "$H7" "$META" install >/dev/null

user_sidecar="$H7/.cursor/.permissions.user-managed.json"
[ -f "$user_sidecar" ] || fail "T07: user-managed sidecar not created"
has_extra=$(jq '.terminalAllowlist | contains(["user-added-cmd"])' "$user_sidecar")
[ "$has_extra" = "true" ] || fail "T07: user entry not captured in user-managed sidecar"

# The entry must survive in the live file.
still_has=$(jq '.terminalAllowlist | contains(["user-added-cmd"])' "$H7/.cursor/permissions.json")
[ "$still_has" = "true" ] || fail "T07: user entry lost from live file after re-render"

# ---------------------------------------------------------------------------
# T08: Two-installer coexistence — agerpoint + personal entries both present;
#      uninstalling one preserves the other's entries.
# ---------------------------------------------------------------------------
printf '[T08] two-installer coexistence\n'
H8=$(mk_home t08)
run_al     "$H8" "$META"  install >/dev/null
run_al_org "testpeer" "$H8" "$META2" install >/dev/null

# Both sets of entries must be in the live permissions.json.
has_git=$(jq '.terminalAllowlist | contains(["git status"])' "$H8/.cursor/permissions.json")
has_pytest=$(jq '.terminalAllowlist | contains(["pytest"])'  "$H8/.cursor/permissions.json")
[ "$has_git"    = "true" ] || fail "T08: agerpoint entry missing after coexistence install"
[ "$has_pytest" = "true" ] || fail "T08: personal entry missing after coexistence install"

# Claude settings should also have both orgs' MCP entries.
has_notion=$(jq '.permissions.allow | contains(["mcp__notion__*"])' "$H8/.claude/settings.json")
has_miro=$(jq   '.permissions.allow | contains(["mcp__miro-mcp__*"])' "$H8/.claude/settings.json")
[ "$has_notion" = "true" ] || fail "T08: agerpoint MCP entry missing from settings.json"
[ "$has_miro"   = "true" ] || fail "T08: personal MCP entry missing from settings.json"

# Uninstall $ORG only — testpeer entries must survive.
run_al "$H8" "$META" uninstall >/dev/null

has_git2=$(jq    '.terminalAllowlist | contains(["git status"])' "$H8/.cursor/permissions.json")
has_pytest2=$(jq '.terminalAllowlist | contains(["pytest"])'     "$H8/.cursor/permissions.json")
[ "$has_git2"    = "false" ] || fail "T08: agerpoint entry still present after agerpoint uninstall"
[ "$has_pytest2" = "true"  ] || fail "T08: personal entry lost after agerpoint uninstall"

# ---------------------------------------------------------------------------
# T09: Uninstall semantics (default KEEP) — with REMOVE_HISTORY=no the
#      sidecar is removed and user-managed sidecar preserved, but .history/
#      is kept.
# ---------------------------------------------------------------------------
printf '[T09] uninstall semantics (default keep)\n'
H9=$(mk_home t09)
# Two installs with different meta sources to create rotation entries.
run_al "$H9" "$TEST_DIR/meta/v1.json" install >/dev/null
run_al "$H9" "$TEST_DIR/meta/v2.json" install >/dev/null

[ -d "$H9/.cursor/.history" ] || fail "T09: .history/ was not created (setup issue)"
backup1="$H9/.cursor/.history/permissions.json.1"
[ -f "$backup1" ] || fail "T09: permissions.json.1 not present before uninstall (setup issue)"

# Plant a user-managed sidecar so we can verify it survives.
user_sidecar="$H9/.cursor/.permissions.user-managed.json"
printf '{"terminalAllowlist":["my-user-entry"]}\n' > "$user_sidecar"

# Default keep path (run_al passes REMOVE_HISTORY=no).
run_al "$H9" "$TEST_DIR/meta/v2.json" uninstall >/dev/null

# .history/ must still exist when the engineer declines removal.
[ -d "$H9/.cursor/.history"   ] || fail "T09: .history/ was purged despite REMOVE_HISTORY=no"
# Agerpoint sidecar must be gone.
sidecar="$H9/.cursor/.permissions.${ORG}-managed.json"
[ ! -f "$sidecar"             ] || fail "T09: $ORG sidecar not removed by uninstall"
# User-managed sidecar must survive.
[ -f "$user_sidecar"          ] || fail "T09: user-managed sidecar was removed by uninstall"

# ---------------------------------------------------------------------------
# T10: diff — reports differences between expected and live
# ---------------------------------------------------------------------------
printf '[T10] diff\n'
H10=$(mk_home t10)
run_al "$H10" "$META" install >/dev/null

# Tamper with the live file.
jq 'del(.terminalAllowlist)' "$H10/.cursor/permissions.json" \
    > "$H10/.cursor/permissions.json.tmp"
mv "$H10/.cursor/permissions.json.tmp" "$H10/.cursor/permissions.json"

diff_out=$(run_al "$H10" "$META" diff 2>&1 || true)
# diff output should mention the file and show it differs.
case "$diff_out" in
    *"permissions.json"*) ;;
    *) fail "T10: diff output does not mention permissions.json" ;;
esac
# "~ differs:" appears when the files differ; its absence means a false match.
case "$diff_out" in
    *"differs:"*) ;;
    *) fail "T10: diff did not report differs: after tampering (output: $diff_out)" ;;
esac

# ---------------------------------------------------------------------------
# T11: restore round-trip — restore-allowlists N=1 brings back a backup
# ---------------------------------------------------------------------------
printf '[T11] restore round-trip\n'
H11=$(mk_home t11)
run_al "$H11" "$META" install >/dev/null

# Remember the initial rendered content.
original_content=$(cat "$H11/.cursor/permissions.json")

# Change the meta so the next install writes different content.
META_ALT="$TEST_DIR/meta/alt.json"
printf '{"shell":{"allow":["alt-cmd"],"deny":[]},"mcp":{"allow":[],"deny":[]},"read":{"deny":[]},"write":{"deny":[]},"webfetch":{"allow":[],"deny":[]}}\n' \
    > "$META_ALT"
run_al "$H11" "$META_ALT" install >/dev/null
[ -f "$H11/.cursor/.history/permissions.json.1" ] || fail "T11: no backup before restore"

# Restore to backup .1.
ORG="$ORG" \
ALLOWLISTS_SRC="$META_ALT" \
CURSOR_DATA_HOME="$H11/.cursor" \
CLAUDE_DATA_HOME="$H11/.claude" \
RESTORE_N=1 \
bash "$ALLOWLISTS" restore >/dev/null

restored=$(cat "$H11/.cursor/permissions.json")
[ "$restored" = "$original_content" ] || fail "T11: restored content does not match original"

# A new .history/permissions.json.1 should now hold the pre-restore live file.
[ -f "$H11/.cursor/.history/permissions.json.2" ] || fail "T11: pre-restore file not backed up as .2"

# ---------------------------------------------------------------------------
# T12: clean-allowlists — removes .history/ dirs only when explicitly invoked
# ---------------------------------------------------------------------------
printf '[T12] clean-allowlists\n'
H12=$(mk_home t12)
# Use two different meta sources to force rotation and create .history/.
run_al "$H12" "$TEST_DIR/meta/v1.json" install >/dev/null
run_al "$H12" "$TEST_DIR/meta/v2.json" install >/dev/null
[ -d "$H12/.cursor/.history" ] || fail "T12: .history/ setup failed"

run_al "$H12" "$META" clean >/dev/null

[ ! -d "$H12/.cursor/.history" ] || fail "T12: .cursor/.history/ not removed by clean"
[ ! -d "$H12/.claude/.history" ] || fail "T12: .claude/.history/ not removed by clean"
# Live files must still exist.
[ -f "$H12/.cursor/permissions.json" ] || fail "T12: permissions.json removed by clean (must not be)"

# ---------------------------------------------------------------------------
# T13: Foreign-file detection — a non-installer file in .history/ triggers
#      a note in status output but does not abort.
# ---------------------------------------------------------------------------
printf '[T13] foreign-file detection\n'
H13=$(mk_home t13)
# Force .history/ creation by running two installs.
run_al "$H13" "$TEST_DIR/meta/v1.json" install >/dev/null
run_al "$H13" "$TEST_DIR/meta/v2.json" install >/dev/null
[ -d "$H13/.cursor/.history" ] || fail "T13: .history/ setup failed"

# Drop a foreign file into .history/.
printf 'not-managed-by-installer\n' > "$H13/.cursor/.history/something-else.txt"

status_out=$(run_al "$H13" "$META" status 2>&1)
case "$status_out" in
    *"foreign"*|*"something-else"*) ;;
    *) fail "T13: status did not report foreign file in .history/" ;;
esac

# ---------------------------------------------------------------------------
# T14: CLI passthrough — non-permission keys (version, editor) survive
#      a render of cli-config.json via the passthrough sidecar.
# ---------------------------------------------------------------------------
printf '[T14] CLI passthrough\n'
H14=$(mk_home t14)
# Pre-seed cli-config.json with extra non-permission keys.
printf '{"version":"1.2","editor":"cursor","permissions":{"allow":[],"deny":[]}}\n' \
    > "$H14/.cursor/cli-config.json"

run_al "$H14" "$META" install >/dev/null

# The passthrough sidecar should have been created.
pt="$H14/.cursor/.cli-config.passthrough.json"
[ -f "$pt" ] || fail "T14: .cli-config.passthrough.json not created"
v=$(jq -r '.version // empty' "$pt")
[ "$v" = "1.2" ] || fail "T14: version not captured in passthrough sidecar (got: $v)"

# The rendered cli-config.json must still carry version and editor.
v2=$(jq -r '.version // empty' "$H14/.cursor/cli-config.json")
e2=$(jq -r '.editor  // empty' "$H14/.cursor/cli-config.json")
[ "$v2" = "1.2"    ] || fail "T14: version lost from rendered cli-config.json (got: $v2)"
[ "$e2" = "cursor" ] || fail "T14: editor lost from rendered cli-config.json (got: $e2)"

# Deny entries must also appear in cli-config.json.
has_deny=$(jq '.permissions.deny | contains(["rm -rf /"])' "$H14/.cursor/cli-config.json")
[ "$has_deny" = "true" ] || fail "T14: deny entry missing from cli-config.json"

# ---------------------------------------------------------------------------
# T15: Claude format translation — mcp entries use mcp__server__* form,
#      webfetch entries use WebFetch(domain:...) form.
# ---------------------------------------------------------------------------
printf '[T15] Claude format translation\n'
H15=$(mk_home t15)
run_al "$H15" "$META" install >/dev/null

has_notion=$(jq '.permissions.allow | contains(["mcp__notion__*"])' "$H15/.claude/settings.json")
has_slack=$(jq  '.permissions.allow | contains(["mcp__slack__*"])'  "$H15/.claude/settings.json")
has_wf=$(jq     '.permissions.allow | contains(["WebFetch(domain:*.github.com)"])' \
                "$H15/.claude/settings.json")
has_deny=$(jq   '.permissions.deny  | contains(["rm -rf /"])'       "$H15/.claude/settings.json")

[ "$has_notion" = "true" ] || fail "T15: mcp__notion__* missing from settings.json"
[ "$has_slack"  = "true" ] || fail "T15: mcp__slack__* missing from settings.json"
[ "$has_wf"     = "true" ] || fail "T15: WebFetch(domain:*.github.com) missing from settings.json"
[ "$has_deny"   = "true" ] || fail "T15: shell deny entry missing from settings.json"

# Raw colon-notation must NOT appear in the Claude output.
raw=$(jq '.permissions.allow | map(select(test("^notion:"))) | length' "$H15/.claude/settings.json")
[ "$raw" = "0" ] || fail "T15: raw 'notion:*' notation found in settings.json (should be mcp__notion__*)"

# ---------------------------------------------------------------------------
# T16: Flock serialization — two concurrent installs both succeed without
#      corrupting the rendered files.
# ---------------------------------------------------------------------------
printf '[T16] flock serialization\n'
H16=$(mk_home t16)
run_al "$H16" "$META" install >/dev/null  # warm up (files exist)

out1="$TEST_DIR/lock1.out"
out2="$TEST_DIR/lock2.out"

rc1=0; rc2=0
run_al "$H16" "$META" install >"$out1" 2>&1 &
PID1=$!
run_al "$H16" "$META" install >"$out2" 2>&1 &
PID2=$!

wait "$PID1" || rc1=$?
wait "$PID2" || rc2=$?

[ "$rc1" -eq 0 ] || fail "T16: first concurrent install failed (rc=$rc1)"
[ "$rc2" -eq 0 ] || fail "T16: second concurrent install failed (rc=$rc2)"

jq . "$H16/.cursor/permissions.json" >/dev/null 2>&1 || fail "T16: permissions.json corrupted"
jq . "$H16/.cursor/cli-config.json"  >/dev/null 2>&1 || fail "T16: cli-config.json corrupted"
jq . "$H16/.claude/settings.json"    >/dev/null 2>&1 || fail "T16: settings.json corrupted"

# ---------------------------------------------------------------------------
# T17: Uninstall removal path — REMOVE_HISTORY=yes purges .history/ on a
#      successful uninstall.
# ---------------------------------------------------------------------------
printf '[T17] uninstall removes .history (REMOVE_HISTORY=yes)\n'
H17=$(mk_home t17)
run_al "$H17" "$TEST_DIR/meta/v1.json" install >/dev/null
run_al "$H17" "$TEST_DIR/meta/v2.json" install >/dev/null
[ -d "$H17/.cursor/.history" ] || fail "T17: .history/ setup failed"

REMOVE_HISTORY=yes run_al "$H17" "$TEST_DIR/meta/v2.json" uninstall >/dev/null

[ ! -d "$H17/.cursor/.history" ] || fail "T17: .cursor/.history/ not removed with REMOVE_HISTORY=yes"
[ ! -d "$H17/.claude/.history" ] || fail "T17: .claude/.history/ not removed with REMOVE_HISTORY=yes"

# ---------------------------------------------------------------------------
# Windows dual-pass tests (sandboxed WIN_HOME — no real WSL required)
# ---------------------------------------------------------------------------

# Create a fake Windows home directory with .cursor/ and .claude/ subdirs.
mk_win_home() {
    local d="$TEST_DIR/homes/$1"
    mkdir -p "$d/.cursor" "$d/.claude"
    printf '%s' "$d"
}

# ---------------------------------------------------------------------------
# T18: Dual-pass install — both unix and Windows files created, byte-identical.
# ---------------------------------------------------------------------------
printf '[T18] dual-pass install: unix and Windows files byte-identical\n'
H18=$(mk_home t18)
W18=$(mk_win_home t18w)
run_al_win "$H18" "$W18" "$META" install >/dev/null

[ -f "$H18/.cursor/permissions.json" ] || fail "T18: unix permissions.json not created"
[ -f "$W18/.cursor/permissions.json" ] || fail "T18: win permissions.json not created"
cmp -s "$H18/.cursor/permissions.json" "$W18/.cursor/permissions.json" \
    || fail "T18: unix and Windows permissions.json differ"

[ -f "$H18/.cursor/cli-config.json" ] || fail "T18: unix cli-config.json not created"
[ -f "$W18/.cursor/cli-config.json" ] || fail "T18: win cli-config.json not created"
cmp -s "$H18/.cursor/cli-config.json" "$W18/.cursor/cli-config.json" \
    || fail "T18: unix and Windows cli-config.json differ"

[ -f "$H18/.claude/settings.json" ] || fail "T18: unix settings.json not created"
[ -f "$W18/.claude/settings.json" ] || fail "T18: win settings.json not created"
cmp -s "$H18/.claude/settings.json" "$W18/.claude/settings.json" \
    || fail "T18: unix and Windows settings.json differ"

# ---------------------------------------------------------------------------
# T19: Windows-side sidecar is created on install and removed on uninstall.
# ---------------------------------------------------------------------------
printf '[T19] win sidecar create on install, removed on uninstall\n'
H19=$(mk_home t19)
W19=$(mk_win_home t19w)
run_al_win "$H19" "$W19" "$META" install >/dev/null

[ -f "$W19/.cursor/.permissions.${ORG}-managed.json" ] \
    || fail "T19: win .cursor permissions sidecar not created"
[ -f "$W19/.claude/.settings.${ORG}-managed.json" ] \
    || fail "T19: win .claude settings sidecar not created"

run_al_win "$H19" "$W19" "$META" uninstall >/dev/null

[ ! -f "$W19/.cursor/.permissions.${ORG}-managed.json" ] \
    || fail "T19: win .cursor permissions sidecar not removed on uninstall"
[ ! -f "$W19/.claude/.settings.${ORG}-managed.json" ] \
    || fail "T19: win .claude settings sidecar not removed on uninstall"

# ---------------------------------------------------------------------------
# T20: Windows-side .history/ rotates independently (per-dir counters).
# ---------------------------------------------------------------------------
printf '[T20] win .history/ rotates independently\n'
H20=$(mk_home t20)
W20=$(mk_win_home t20w)

run_al_win "$H20" "$W20" "$TEST_DIR/meta/v1.json" install >/dev/null
[ ! -d "$W20/.cursor/.history" ] || fail "T20: win .history/ should not exist after v1"

run_al_win "$H20" "$W20" "$TEST_DIR/meta/v2.json" install >/dev/null
[ "$(count_hist permissions "$W20/.cursor")" = "1" ] \
    || fail "T20: expected 1 win backup after v2"

run_al_win "$H20" "$W20" "$TEST_DIR/meta/v3.json" install >/dev/null
[ "$(count_hist permissions "$W20/.cursor")" = "2" ] \
    || fail "T20: expected 2 win backups after v3"

# Unix side should also have rotated independently.
[ "$(count_hist permissions "$H20/.cursor")" = "2" ] \
    || fail "T20: expected 2 unix backups after v3"

# ---------------------------------------------------------------------------
# T21: Windows-side manual-edit is auto-promoted into win user-managed sidecar.
# ---------------------------------------------------------------------------
printf '[T21] win user-edit auto-promotion\n'
H21=$(mk_home t21)
W21=$(mk_win_home t21w)
run_al_win "$H21" "$W21" "$META" install >/dev/null

# Tamper with the Windows permissions.json to add a custom entry.
jq '.terminalAllowlist += ["my-win-tool"]' \
    "$W21/.cursor/permissions.json" > "$W21/.cursor/permissions.json.tmp"
mv "$W21/.cursor/permissions.json.tmp" "$W21/.cursor/permissions.json"

# Re-install; should auto-promote the added entry into the win user-managed sidecar.
run_al_win "$H21" "$W21" "$META" install >/dev/null

user_sidecar="$W21/.cursor/.permissions.user-managed.json"
[ -f "$user_sidecar" ] || fail "T21: win user-managed sidecar not created"
jq -e '.terminalAllowlist | index("my-win-tool") != null' "$user_sidecar" >/dev/null \
    || fail "T21: win user-edit not promoted into user-managed sidecar"

# ---------------------------------------------------------------------------
# T22: WIN_HOME unset → only unix targets touched (regression guard).
# ---------------------------------------------------------------------------
printf '[T22] WIN_HOME unset → only unix targets touched\n'
H22=$(mk_home t22)
W22=$(mk_win_home t22w)

# Install without WIN_HOME.
run_al "$H22" "$META" install >/dev/null

[ -f  "$H22/.cursor/permissions.json" ] || fail "T22: unix permissions.json not created"
[ ! -f "$W22/.cursor/permissions.json" ] || fail "T22: win permissions.json must not be created when WIN_HOME unset"
[ ! -f "$W22/.claude/settings.json"   ] || fail "T22: win settings.json must not be created when WIN_HOME unset"

# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------
if [ "$FAILED" -eq 0 ]; then
    printf '\nAll tests passed.\n'
else
    printf '\n%d test(s) FAILED.\n' "$FAILED" >&2
    exit 1
fi
