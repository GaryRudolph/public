#!/usr/bin/env bash
# Test harness for allowlists.sh. Builds sandboxed fake home directories and
# a fake meta-source JSON, then exercises every subcommand and edge case:
# first-install (with and without prior file), idempotence, rotation across
# gaps, unbounded growth, user-edit auto-promotion, two-installer coexistence,
# uninstall semantics, diff/restore round-trip, clean, foreign-file detection,
# flock serialization, CLI passthrough, Claude format translation, Windows
# dual-pass (via a sandboxed WIN_HOME — no real WSL required), and the Gemini
# Policy Engine TOML render path (create, deny mapping, idempotence, rotation,
# uninstall + peer coexistence, dual-pass, restore, WIN_HOME gating, clean),
# and the upgrade that clears what earlier versions rendered into Claude
# Code's settings.json (Claude Code's rules are org managed settings now).
#
# All assertions are local to the sandbox. Every runner pins GEMINI_DATA_HOME
# (and WIN_GEMINI_DATA_HOME) into the sandbox too, so the real ~/.gemini is
# never touched. Never touches the real $HOME.
#
# Required env (set by the calling Makefile):
#   ORG        - "agerpoint" or "personal"
#   AGENTS_DIR - absolute path to the agents/ dir

set -euo pipefail
# The real config dirs must stay out of the sandbox: the dotfiles export
# CLAUDE_CONFIG_DIRS, and the lib scripts and the Makefile default from it.
unset CLAUDE_CONFIG_DIRS CLAUDE_CONFIG_DIR

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
  "mcp":      { "allow": ["notion:*", "slack:*", "figma:get_screenshot"], "deny": [] },
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

# Claude Code's rules as the managed settings render them (agents/org/render.sh):
# allowlist.jq's claude_permissions on a meta. The installer no longer writes them.
claude_render() {
    jq -S "$(cat "$AGENTS_DIR/lib/allowlist.jq")"'claude_permissions' "$1"
}

# Create a fresh home-like directory with .cursor/, .claude/, and .gemini/ subdirs.
mk_home() {
    local d="$TEST_DIR/homes/$1"
    mkdir -p "$d/.cursor" "$d/.claude" "$d/.gemini"
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
    CLAUDE_CONFIG_DIRS="$home/.claude" \
    GEMINI_DATA_HOME="$home/.gemini" \
    REMOVE_HISTORY="${REMOVE_HISTORY:-no}" \
    bash "$ALLOWLISTS" "$@"
}

# Run with a specific ORG override (for coexistence tests).
run_al_org() {
    local org_val="$1" home="$2" meta="$3"; shift 3
    ORG="$org_val" \
    ALLOWLISTS_SRC="$meta" \
    CURSOR_DATA_HOME="$home/.cursor" \
    CLAUDE_CONFIG_DIRS="$home/.claude" \
    GEMINI_DATA_HOME="$home/.gemini" \
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
    CLAUDE_CONFIG_DIRS="$home/.claude" \
    GEMINI_DATA_HOME="$home/.gemini" \
    WIN_HOME="$win_home" \
    WIN_CURSOR_DATA_HOME="$win_home/.cursor" \
    WIN_CLAUDE_DATA_HOME="$win_home/.claude" \
    WIN_GEMINI_DATA_HOME="$win_home/.gemini" \
    REMOVE_HISTORY="${REMOVE_HISTORY:-no}" \
    bash "$ALLOWLISTS" "$@"
}

# Count .N backup files for a stem+parent combination (JSON targets).
count_hist() {
    local stem="$1" parent="$2"
    find "$parent/.history" -maxdepth 1 -name "${stem}.json.[0-9]*" -type f 2>/dev/null \
        | wc -l | tr -d ' '
}

# Count .N backup files for an arbitrary base filename (e.g. the Gemini
# <org>-managed.toml) under $parent/.history.
count_hist_ext() {
    local base="$1" parent="$2"
    find "$parent/.history" -maxdepth 1 -name "${base}.[0-9]*" -type f 2>/dev/null \
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
[ ! -d "$H/.cursor/.history"       ] || fail "T01: .cursor/.history/ must not be created on first install"
# Claude Code's rules come from managed settings: nothing lands in its config dir.
[ -z "$(ls -A "$H/.claude")"       ] || fail "T01: install wrote into .claude/: $(ls -A "$H/.claude")"
# Rendered files must be valid JSON.
jq . "$H/.cursor/permissions.json" >/dev/null 2>&1 || fail "T01: permissions.json invalid JSON"
jq . "$H/.cursor/cli-config.json"  >/dev/null 2>&1 || fail "T01: cli-config.json invalid JSON"

# ---------------------------------------------------------------------------
# T02: Idempotence — second install is a no-op (no new .history entries)
# ---------------------------------------------------------------------------
printf '[T02] idempotence\n'
snap_p=$(cat "$H/.cursor/permissions.json")
snap_c=$(cat "$H/.cursor/cli-config.json")
run_al "$H" "$META" install >/dev/null
[ "$(cat "$H/.cursor/permissions.json")" = "$snap_p" ] || fail "T02: permissions.json changed"
[ "$(cat "$H/.cursor/cli-config.json")"  = "$snap_c" ] || fail "T02: cli-config.json changed"
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
# Nothing is written to the Claude config dir, so no claude .history/ either.
[ ! -d "$H3/.claude/.history"                         ] || fail "T03: claude .history/ created"

# ---------------------------------------------------------------------------
# T04: First-install conflict guardrail — abort when .history/.1 exists with
#      no agerpoint sidecar (paranoia: some other tool managed this file).
# ---------------------------------------------------------------------------
printf '[T04] first-install conflict guardrail\n'
H4=$(mk_home t04)
mkdir -p "$H4/.cursor/.history"
printf '{"terminalAllowlist":["foreign-entry"]}\n' \
    > "$H4/.cursor/.history/permissions.json.1"
# A hand-written live file that no sidecar explains → refuse, exit non-zero,
# leave the file byte-identical.
printf '{"terminalAllowlist":["hand-written"]}\n' > "$H4/.cursor/permissions.json"
cp "$H4/.cursor/permissions.json" "$TEST_DIR/t04.before"
rc=0
run_al "$H4" "$META" install >/dev/null 2>/dev/null || rc=$?
[ "$rc" -ne 0 ] || fail "T04: install should have aborted (got exit 0)"
cmp -s "$TEST_DIR/t04.before" "$H4/.cursor/permissions.json" \
    || fail "T04: hand-written permissions.json must be left untouched after abort"

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
CLAUDE_CONFIG_DIRS="$H11/.claude" \
GEMINI_DATA_HOME="$H11/.gemini" \
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

# Deny entries must also appear in cli-config.json, in the prefix form Cursor
# CLI reads (a bare "rm -rf /" is matched by nothing there).
has_deny=$(jq '.permissions.deny | index("Shell(rm:-rf /*)") != null' "$H14/.cursor/cli-config.json")
[ "$has_deny" = "true" ] || fail "T14: Shell(rm:-rf /*) deny missing from cli-config.json"
bare=$(jq '[.permissions.allow[], .permissions.deny[] | select(test("^(Shell|Mcp)\\(") | not)] | length' "$H14/.cursor/cli-config.json")
[ "$bare" = "0" ] || fail "T14: bare (unwrapped) entry in cli-config.json permissions"

# ---------------------------------------------------------------------------
# T15: Claude format translation (allowlist.jq's claude_permissions, which the
#      managed settings render) — server:* renders mcp__server__*, server:tool
#      renders mcp__server__tool (never a server wildcard), webfetch entries
#      use WebFetch(domain:...) form. Cursor's forms come from the install.
# ---------------------------------------------------------------------------
printf '[T15] Claude format translation\n'
H15=$(mk_home t15)
run_al "$H15" "$META" install >/dev/null
CC15="$TEST_DIR/t15.claude.json"
claude_render "$META" > "$CC15"

has_notion=$(jq '.permissions.allow | contains(["mcp__notion__*"])' "$CC15")
has_slack=$(jq  '.permissions.allow | contains(["mcp__slack__*"])'  "$CC15")
has_wf=$(jq     '.permissions.allow | contains(["WebFetch(domain:*.github.com)"])' \
                "$CC15")
has_deny=$(jq   '.permissions.deny  | index("Bash(rm -rf /:*)") != null' "$CC15")

[ "$has_notion" = "true" ] || fail "T15: mcp__notion__* missing from the Claude render"
[ "$has_slack"  = "true" ] || fail "T15: mcp__slack__* missing from the Claude render"
[ "$has_wf"     = "true" ] || fail "T15: WebFetch(domain:*.github.com) missing from the Claude render"
[ "$has_deny"   = "true" ] || fail "T15: Bash(rm -rf /:*) deny missing from the Claude render"
has_allow=$(jq  '.permissions.allow | index("Bash(git status)") != null' "$CC15")
[ "$has_allow"  = "true" ] || fail "T15: exact Bash(git status) allow missing from the Claude render"
bare=$(jq '[.permissions.allow[], .permissions.deny[] | select(test("^(Bash|mcp__|WebFetch)") | not)] | length' "$CC15")
[ "$bare" = "0" ] || fail "T15: bare (unwrapped) entry in the Claude render permissions"

# A named tool renders per tool in Claude Code and Cursor CLI, and keeps its
# server:tool form in Cursor IDE; it must not widen to the whole server (r1.f9).
has_shot=$(jq '.permissions.allow | contains(["mcp__figma__get_screenshot"])' "$CC15")
has_figma_all=$(jq '.permissions.allow | contains(["mcp__figma__*"])' "$CC15")
[ "$has_shot" = "true" ]       || fail "T15: mcp__figma__get_screenshot missing from the Claude render"
[ "$has_figma_all" = "false" ] || fail "T15: figma:get_screenshot widened to mcp__figma__* in the Claude render"
[ "$(jq '.permissions.allow | contains(["Mcp(figma:get_screenshot)"])' "$H15/.cursor/cli-config.json")" = "true" ] \
    || fail "T15: Mcp(figma:get_screenshot) missing from cli-config.json"
[ "$(jq '.permissions.allow | contains(["Mcp(figma:*)"])' "$H15/.cursor/cli-config.json")" = "false" ] \
    || fail "T15: figma:get_screenshot widened to Mcp(figma:*) in cli-config.json"
[ "$(jq '.mcpAllowlist | contains(["figma:get_screenshot"])' "$H15/.cursor/permissions.json")" = "true" ] \
    || fail "T15: figma:get_screenshot missing from permissions.json mcpAllowlist"
[ "$(jq '.mcpAllowlist | contains(["figma:*"])' "$H15/.cursor/permissions.json")" = "false" ] \
    || fail "T15: figma:get_screenshot widened to figma:* in permissions.json"

# Raw colon-notation must NOT appear in the Claude output.
raw=$(jq '.permissions.allow | map(select(test("^notion:"))) | length' "$CC15")
[ "$raw" = "0" ] || fail "T15: raw 'notion:*' notation found in the Claude render (should be mcp__notion__*)"

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

[ ! -e "$H18/.claude/settings.json" ] || fail "T18: unix settings.json written"
[ ! -e "$W18/.claude/settings.json" ] || fail "T18: win settings.json written"

# ---------------------------------------------------------------------------
# T19: Windows-side sidecar is created on install and removed on uninstall.
# ---------------------------------------------------------------------------
printf '[T19] win sidecar create on install, removed on uninstall\n'
H19=$(mk_home t19)
W19=$(mk_win_home t19w)
run_al_win "$H19" "$W19" "$META" install >/dev/null

[ -f "$W19/.cursor/.permissions.${ORG}-managed.json" ] \
    || fail "T19: win .cursor permissions sidecar not created"

run_al_win "$H19" "$W19" "$META" uninstall >/dev/null

[ ! -f "$W19/.cursor/.permissions.${ORG}-managed.json" ] \
    || fail "T19: win .cursor permissions sidecar not removed on uninstall"

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
# Gemini Policy Engine TOML render path
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# T23: Gemini first-install → <org>-managed.toml created, no .history/
# ---------------------------------------------------------------------------
printf '[T23] gemini first-install: managed .toml created, no .history\n'
H23=$(mk_home t23)
run_al "$H23" "$META" install >/dev/null
GTOML23="$H23/.gemini/policies/${ORG}-managed.toml"
[ -f "$GTOML23" ] || fail "T23: gemini managed .toml not created"
[ ! -d "$H23/.gemini/policies/.history" ] || fail "T23: gemini .history must not be created on first install"
grep -q '^\[\[rule\]\]' "$GTOML23" || fail "T23: no [[rule]] blocks in managed .toml"
grep -qF 'commandPrefix = "git status"' "$GTOML23" || fail "T23: allow entry 'git status' missing"
grep -qF 'commandPrefix = "make test"'  "$GTOML23" || fail "T23: allow entry 'make test' missing"
grep -qF 'toolName = "run_shell_command"' "$GTOML23" || fail "T23: toolName line missing"

# ---------------------------------------------------------------------------
# T24: Gemini deny mapping + idempotence
# ---------------------------------------------------------------------------
printf '[T24] gemini deny mapping + idempotence\n'
H24=$(mk_home t24)
run_al "$H24" "$META" install >/dev/null
GTOML24="$H24/.gemini/policies/${ORG}-managed.toml"
grep -qF 'commandPrefix = "rm -rf /"' "$GTOML24" || fail "T24: deny entry 'rm -rf /' missing"
grep -qF 'decision = "deny"'  "$GTOML24" || fail "T24: no deny decision rule"
grep -qF 'priority = 900'     "$GTOML24" || fail "T24: deny priority 900 missing"
grep -qF 'decision = "allow"' "$GTOML24" || fail "T24: no allow decision rule"
grep -qF 'priority = 100'     "$GTOML24" || fail "T24: allow priority 100 missing"
snap_g=$(cat "$GTOML24")
run_al "$H24" "$META" install >/dev/null
[ "$(cat "$GTOML24")" = "$snap_g" ] || fail "T24: gemini .toml changed on idempotent re-install"
[ ! -d "$H24/.gemini/policies/.history" ] || fail "T24: gemini .history created by idempotent install"

# ---------------------------------------------------------------------------
# T25: Gemini rotation on content change
# ---------------------------------------------------------------------------
printf '[T25] gemini rotation on change\n'
H25=$(mk_home t25)
run_al "$H25" "$TEST_DIR/meta/v1.json" install >/dev/null
[ ! -d "$H25/.gemini/policies/.history" ] || fail "T25: gemini .history should not exist after v1"
run_al "$H25" "$TEST_DIR/meta/v2.json" install >/dev/null
[ "$(count_hist_ext "${ORG}-managed.toml" "$H25/.gemini/policies")" = "1" ] \
    || fail "T25: expected 1 gemini backup after v2"
run_al "$H25" "$TEST_DIR/meta/v3.json" install >/dev/null
[ "$(count_hist_ext "${ORG}-managed.toml" "$H25/.gemini/policies")" = "2" ] \
    || fail "T25: expected 2 gemini backups after v3"

# ---------------------------------------------------------------------------
# T26: Gemini uninstall removes our managed file; peer/hand-authored .toml
#      files are left untouched; removed file is recoverable from .history/.
# ---------------------------------------------------------------------------
printf '[T26] gemini uninstall removes managed file; peers untouched\n'
H26=$(mk_home t26)
run_al "$H26" "$META" install >/dev/null
GTOML26="$H26/.gemini/policies/${ORG}-managed.toml"
[ -f "$GTOML26" ] || fail "T26: setup - managed .toml missing"
peer26="$H26/.gemini/policies/testpeer-managed.toml"
hand26="$H26/.gemini/policies/my-own.toml"
printf 'peer\n' > "$peer26"
printf 'hand\n' > "$hand26"
run_al "$H26" "$META" uninstall >/dev/null
[ ! -f "$GTOML26" ] || fail "T26: managed .toml not removed on uninstall"
[ -f "$peer26" ] || fail "T26: peer .toml wrongly removed by uninstall"
[ -f "$hand26" ] || fail "T26: hand-authored .toml wrongly removed by uninstall"
[ -f "$H26/.gemini/policies/.history/${ORG}-managed.toml.1" ] \
    || fail "T26: uninstall did not rotate managed file into .history"

# ---------------------------------------------------------------------------
# T27: Gemini dual-pass — unix and Windows .toml byte-identical.
# ---------------------------------------------------------------------------
printf '[T27] gemini dual-pass: unix and win .toml byte-identical\n'
H27=$(mk_home t27)
W27=$(mk_win_home t27w)
run_al_win "$H27" "$W27" "$META" install >/dev/null
UG27="$H27/.gemini/policies/${ORG}-managed.toml"
WG27="$W27/.gemini/policies/${ORG}-managed.toml"
[ -f "$UG27" ] || fail "T27: unix gemini .toml not created"
[ -f "$WG27" ] || fail "T27: win gemini .toml not created"
cmp -s "$UG27" "$WG27" || fail "T27: unix and win gemini .toml differ"

# ---------------------------------------------------------------------------
# T28: Gemini restore round-trip — restore N=1 brings back a backup.
# ---------------------------------------------------------------------------
printf '[T28] gemini restore round-trip\n'
H28=$(mk_home t28)
run_al "$H28" "$META" install >/dev/null
GTOML28="$H28/.gemini/policies/${ORG}-managed.toml"
original_g=$(cat "$GTOML28")
run_al "$H28" "$META_ALT" install >/dev/null
[ -f "$H28/.gemini/policies/.history/${ORG}-managed.toml.1" ] || fail "T28: no gemini backup before restore"
ORG="$ORG" \
ALLOWLISTS_SRC="$META_ALT" \
CURSOR_DATA_HOME="$H28/.cursor" \
CLAUDE_CONFIG_DIRS="$H28/.claude" \
GEMINI_DATA_HOME="$H28/.gemini" \
RESTORE_N=1 \
bash "$ALLOWLISTS" restore >/dev/null
[ "$(cat "$GTOML28")" = "$original_g" ] || fail "T28: restored gemini .toml does not match original"

# ---------------------------------------------------------------------------
# T29: WIN_HOME unset → only the unix .toml is written (regression guard).
# ---------------------------------------------------------------------------
printf '[T29] gemini: WIN_HOME unset → only unix .toml written\n'
H29=$(mk_home t29)
W29=$(mk_win_home t29w)
run_al "$H29" "$META" install >/dev/null
[ -f  "$H29/.gemini/policies/${ORG}-managed.toml" ] || fail "T29: unix gemini .toml not created"
[ ! -f "$W29/.gemini/policies/${ORG}-managed.toml" ] \
    || fail "T29: win gemini .toml must not be created when WIN_HOME unset"

# ---------------------------------------------------------------------------
# T30: clean removes the Gemini .history/ but keeps the live managed .toml.
# ---------------------------------------------------------------------------
printf '[T30] gemini clean removes .history/, keeps live .toml\n'
H30=$(mk_home t30)
run_al "$H30" "$TEST_DIR/meta/v1.json" install >/dev/null
run_al "$H30" "$TEST_DIR/meta/v2.json" install >/dev/null
[ -d "$H30/.gemini/policies/.history" ] || fail "T30: gemini .history setup failed"
run_al "$H30" "$META" clean >/dev/null
[ ! -d "$H30/.gemini/policies/.history" ] || fail "T30: gemini .history not removed by clean"
[ -f "$H30/.gemini/policies/${ORG}-managed.toml" ] || fail "T30: clean removed the live managed .toml (must not)"

# ---------------------------------------------------------------------------
# T31 (r1.f12): a malformed live file halts install before anything is written.
# ---------------------------------------------------------------------------
printf '[T31] malformed settings.json left to clear: nothing written, exit non-zero\n'
H31=$(mk_home t31)
run_al "$H31" "$META" install >/dev/null
# What an earlier version left: our sidecar beside a settings.json that no
# longer parses. The cleanup reads both, so nothing may be written.
claude_render "$META" > "$H31/.claude/.settings.${ORG}-managed.json"
printf '{"model":"opus","permissions":{"allow":["x"],},}\n' > "$H31/.claude/settings.json"
snap31() { (cd "$H31" && find . -type f -print | LC_ALL=C sort | while IFS= read -r p; do printf '%s %s\n' "$p" "$(cksum < "$p")"; done); }
snap31 > "$TEST_DIR/t31.before"
rc=0
out31=$(run_al "$H31" "$META" install 2>&1) || rc=$?
[ "$rc" -ne 0 ] || fail "T31: install exited 0 on a malformed live file"
snap31 > "$TEST_DIR/t31.after"
cmp -s "$TEST_DIR/t31.before" "$TEST_DIR/t31.after" || fail "T31: a file changed despite the malformed input"
case "$out31" in *"settings.json"*) ;; *) fail "T31: output does not name settings.json" ;; esac

printf '[T31b] 0-byte sidecar: nothing written, exit non-zero\n'
H31B=$(mk_home t31b)
run_al "$H31B" "$META" install >/dev/null
: > "$H31B/.cursor/.cli-config.passthrough.json"
rc=0
run_al "$H31B" "$META" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T31b: install exited 0 with a 0-byte sidecar"
[ -s "$H31B/.cursor/cli-config.json" ] || fail "T31b: cli-config.json was emptied"

# ---------------------------------------------------------------------------
# T32 (r1.f11): an entry removed from the meta leaves the live file.
# ---------------------------------------------------------------------------
printf '[T32] removing an entry from the meta removes it from the live file\n'
H32=$(mk_home t32)
META32A="$TEST_DIR/meta/t32a.json"; META32B="$TEST_DIR/meta/t32b.json"
printf '{"shell":{"allow":["git status","rm"],"deny":[]},"mcp":{"allow":[],"deny":[]},"read":{"deny":[]},"write":{"deny":[]},"webfetch":{"allow":[],"deny":[]}}\n' > "$META32A"
printf '{"shell":{"allow":["git status"],"deny":[]},"mcp":{"allow":[],"deny":[]},"read":{"deny":[]},"write":{"deny":[]},"webfetch":{"allow":[],"deny":[]}}\n' > "$META32B"
run_al "$H32" "$META32A" install >/dev/null
[ "$(jq '.terminalAllowlist | index("rm") | . != null' "$H32/.cursor/permissions.json")" = "true" ] \
    || fail "T32: setup, rm not in permissions.json"
run_al "$H32" "$META32B" install >/dev/null
for f in "$H32/.cursor/permissions.json" "$H32/.cursor/cli-config.json"; do
    grep -q '"rm"\|rm:\*\|Shell(rm' "$f" && fail "T32: rm still live in $(basename "$f")"
done
for f in "$H32/.cursor/.permissions.user-managed.json" "$H32/.cursor/.cli-config.user-managed.json"; do
    if [ -f "$f" ] && grep -q 'rm' "$f"; then
        fail "T32: rm was saved as a user edit in $(basename "$f")"
    fi
done
[ "$(run_al "$H32" "$META32B" status 2>&1 | grep -c 'json OK current')" = "2" ] \
    || fail "T32: status is not OK current on both JSON targets after the removal"

# ---------------------------------------------------------------------------
# T33 (r1.f13): reinstall after uninstall with history kept, and a second org.
# ---------------------------------------------------------------------------
printf '[T33] install, uninstall (history kept), install succeeds\n'
H33=$(mk_home t33)
printf '{"model":"opus"}\n' > "$H33/.claude/settings.json"
run_al "$H33" "$META" install >/dev/null
run_al "$H33" "$META" install >/dev/null
REMOVE_HISTORY=no run_al "$H33" "$META" uninstall >/dev/null
rc=0
run_al "$H33" "$META" install >/dev/null 2>&1 || rc=$?
[ "$rc" -eq 0 ] || fail "T33: reinstall after uninstall failed (exit $rc)"
[ "$(cat "$H33/.claude/settings.json")" = '{"model":"opus"}' ] || fail "T33: settings.json was touched"

printf '[T33b] second org first install after the first org re-rendered\n'
H33B=$(mk_home t33b)
run_al "$H33B" "$META" install >/dev/null
run_al "$H33B" "$TEST_DIR/meta/v1.json" install >/dev/null 2>&1 || true
run_al "$H33B" "$META" install >/dev/null
[ -f "$H33B/.cursor/.history/permissions.json.1" ] || fail "T33b: setup, no history written"
rc=0
run_al_org "testpeer" "$H33B" "$META2" install >/dev/null 2>&1 || rc=$?
[ "$rc" -eq 0 ] || fail "T33b: second org's first install failed (exit $rc)"

# ---------------------------------------------------------------------------
# T34 (r1.f2): permission keys we don't manage survive install.
# ---------------------------------------------------------------------------
printf '[T34] ask, defaultMode, disableBypassPermissionsMode, additionalDirectories survive\n'
H34=$(mk_home t34)
cat > "$H34/.cursor/cli-config.json" <<'ENDJSON'
{"model":"opus","permissions":{"allow":[],"ask":["Bash(git push:*)"],"defaultMode":"acceptEdits","disableBypassPermissionsMode":"disable","additionalDirectories":["/tmp/extra"]}}
ENDJSON
run_al "$H34" "$META" install >/dev/null
run_al "$H34" "$META" install >/dev/null
S34="$H34/.cursor/cli-config.json"
[ "$(jq -c '.permissions.ask' "$S34")" = '["Bash(git push:*)"]' ] || fail "T34: ask lost"
[ "$(jq -r '.permissions.defaultMode' "$S34")" = "acceptEdits" ] || fail "T34: defaultMode lost"
[ "$(jq -r '.permissions.disableBypassPermissionsMode' "$S34")" = "disable" ] || fail "T34: disableBypassPermissionsMode lost"
[ "$(jq -c '.permissions.additionalDirectories' "$S34")" = '["/tmp/extra"]' ] || fail "T34: additionalDirectories lost"
[ "$(jq '.permissions.allow | length > 0' "$S34")" = "true" ] || fail "T34: allow was not rendered"

printf '[T34b] a non-object permissions value is dropped, not merged back\n'
H34B=$(mk_home t34b)
printf '{"model":"opus","permissions":null}\n' > "$H34B/.cursor/cli-config.json"
run_al "$H34B" "$META" install >/dev/null 2>&1 || fail "T34b: install failed on permissions:null"
[ "$(jq '.permissions.allow | length > 0' "$H34B/.cursor/cli-config.json")" = "true" ] \
    || fail "T34b: allow not rendered over permissions:null"

# ---------------------------------------------------------------------------
# T35 (review): a setting the engineer removes does not come back from a stale passthrough.
# ---------------------------------------------------------------------------
printf '[T35] removing the last unmanaged setting clears the passthrough\n'
H35=$(mk_home t35)
printf '{"permissions":{"defaultMode":"bypassPermissions"}}\n' > "$H35/.cursor/cli-config.json"
run_al "$H35" "$META" install >/dev/null
[ "$(jq -r '.permissions.defaultMode' "$H35/.cursor/cli-config.json")" = "bypassPermissions" ] || fail "T35: setup, defaultMode not kept"
jq 'del(.permissions.defaultMode)' "$H35/.cursor/cli-config.json" > "$H35/s.tmp" && mv "$H35/s.tmp" "$H35/.cursor/cli-config.json"
run_al "$H35" "$META" install >/dev/null
[ "$(jq -r '.permissions.defaultMode // "gone"' "$H35/.cursor/cli-config.json")" = "gone" ] \
    || fail "T35: defaultMode came back after the engineer removed it"

# ---------------------------------------------------------------------------
# T36 (review): a backup that looks like a sidecar does not satisfy the guard.
# ---------------------------------------------------------------------------
printf '[T36] stray .permissions.backup.json does not explain a hand-written live file\n'
H36=$(mk_home t36)
mkdir -p "$H36/.cursor/.history"
printf '{"terminalAllowlist":["old"]}\n' > "$H36/.cursor/.history/permissions.json.1"
printf '{"terminalAllowlist":["hand-written"]}\n' > "$H36/.cursor/permissions.json"
printf '{}\n' > "$H36/.cursor/.permissions.backup.json"
rc=0
run_al "$H36" "$META" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T36: guard bypassed by a stray backup file"
[ "$(jq -r '.terminalAllowlist[0]' "$H36/.cursor/permissions.json")" = "hand-written" ] || fail "T36: live file was rewritten"

# ---------------------------------------------------------------------------
# T37 (review): live files that are not exactly one object with array lists are refused untouched.
# ---------------------------------------------------------------------------
printf '[T37] whitespace, two values, a top-level array, string lists: refused, untouched\n'
n=0
for content in '   ' '{"a":1}{"b":2}' '[1,2]' '{"permissions":{"allow":"Bash(x)"}}'; do
    n=$((n + 1))
    H37=$(mk_home "t37-$n")
    printf '%s\n' "$content" > "$H37/.cursor/cli-config.json"
    cp "$H37/.cursor/cli-config.json" "$TEST_DIR/t37.before"
    rc=0
    run_al "$H37" "$META" install >/dev/null 2>&1 || rc=$?
    [ "$rc" -ne 0 ] || fail "T37.$n: install exited 0"
    cmp -s "$TEST_DIR/t37.before" "$H37/.cursor/cli-config.json" || fail "T37.$n: cli-config.json changed"
    [ -z "$(find "$H37/.cursor" -name '.cli-config.*' -print -quit)" ] || fail "T37.$n: a sidecar was written"
done
H37C=$(mk_home t37-cursor)
printf '{"terminalAllowlist":"git"}\n' > "$H37C/.cursor/permissions.json"
rc=0
run_al "$H37C" "$META" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T37c: install exited 0 on a string terminalAllowlist"

# ---------------------------------------------------------------------------
# T38 (review): a meta that prints a render and then fails writes nothing, promotion included.
# ---------------------------------------------------------------------------
printf '[T38] meta with trailing garbage: nothing written\n'
H38=$(mk_home t38)
{ cat "$META"; printf 'garbage\n'; } > "$TEST_DIR/meta/t38.json"
printf '{"model":"opus"}\n' > "$H38/.cursor/cli-config.json"
cp "$H38/.cursor/cli-config.json" "$TEST_DIR/t38.before"
rc=0
run_al "$H38" "$TEST_DIR/meta/t38.json" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T38: install exited 0 on a bad meta"
cmp -s "$TEST_DIR/t38.before" "$H38/.cursor/cli-config.json" || fail "T38: cli-config.json changed"
[ -z "$(find "$H38/.cursor" -name '.cli-config.*' -print -quit)" ] || fail "T38: a sidecar was written"

# ---------------------------------------------------------------------------
# T39 (review round 2): uninstall validates first, and a stray backup does not block reinstall.
# ---------------------------------------------------------------------------
printf '[T39] uninstall refuses a live file with two JSON values, untouched\n'
H39=$(mk_home t39)
run_al "$H39" "$META" install >/dev/null
printf '{"a":1}{"b":2}\n' > "$H39/.cursor/cli-config.json"
cp "$H39/.cursor/cli-config.json" "$TEST_DIR/t39.before"
rc=0
run_al "$H39" "$META" uninstall >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T39: uninstall exited 0 on a malformed live file"
cmp -s "$TEST_DIR/t39.before" "$H39/.cursor/cli-config.json" || fail "T39: cli-config.json changed"
[ -f "$H39/.cursor/.cli-config.${ORG}-managed.json" ] || fail "T39: org sidecar removed despite the abort"

printf '[T39b] stray backup file: install, uninstall, reinstall succeeds\n'
H39B=$(mk_home t39b)
run_al "$H39B" "$META" install >/dev/null
printf '{}\n' > "$H39B/.cursor/.permissions.backup.json"
run_al "$H39B" "$META" install >/dev/null
REMOVE_HISTORY=no run_al "$H39B" "$META" uninstall >/dev/null
rc=0
run_al "$H39B" "$META" install >/dev/null 2>&1 || rc=$?
[ "$rc" -eq 0 ] || fail "T39b: reinstall failed with a stray backup present (exit $rc)"

printf '[T39c] empty symlinked sidecar is caught before any write\n'
H39C=$(mk_home t39c)
run_al "$H39C" "$META" install >/dev/null
: > "$TEST_DIR/t39c.empty"
ln -sf "$TEST_DIR/t39c.empty" "$H39C/.cursor/.cli-config.user-managed.json"
snap39() { (cd "$H39C" && find . -type f -print | LC_ALL=C sort | while IFS= read -r p; do printf '%s %s\n' "$p" "$(cksum < "$p")"; done); }
snap39 > "$TEST_DIR/t39c.before"
rc=0
run_al "$H39C" "$META2" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T39c: install exited 0 with an empty symlinked sidecar"
snap39 > "$TEST_DIR/t39c.after"
cmp -s "$TEST_DIR/t39c.before" "$TEST_DIR/t39c.after" || fail "T39c: a file changed despite the abort"

printf '[T39d] dry-run previews the stale passthrough as gone\n'
H39D=$(mk_home t39d)
printf '{"permissions":{"defaultMode":"bypassPermissions"}}\n' > "$H39D/.cursor/cli-config.json"
run_al "$H39D" "$META" install >/dev/null
jq 'del(.permissions.defaultMode)' "$H39D/.cursor/cli-config.json" > "$H39D/s.tmp" && mv "$H39D/s.tmp" "$H39D/.cursor/cli-config.json"
run_al "$H39D" "$META" dry-run 2>&1 | grep -F 'cli-config.json' | grep -q 'no change' \
    || fail "T39d: dry-run previews a rewrite that install would not make"

# ---------------------------------------------------------------------------
# T40 (review round 3)
# ---------------------------------------------------------------------------
printf '[T40] dry-run previews a changed, non-empty passthrough, not the stale one\n'
H40=$(mk_home t40)
printf '{"model":"opus","permissions":{"defaultMode":"bypassPermissions"}}\n' > "$H40/.cursor/cli-config.json"
run_al "$H40" "$META" install >/dev/null
jq 'del(.permissions.defaultMode)' "$H40/.cursor/cli-config.json" > "$H40/s.tmp" && mv "$H40/s.tmp" "$H40/.cursor/cli-config.json"
run_al "$H40" "$META" dry-run 2>&1 | grep -F 'cli-config.json' | grep -q 'no change' \
    || fail "T40: dry-run previews a rewrite install would not make"
[ "$(jq -r '.permissions.defaultMode // "gone"' "$H40/.cursor/.cli-config.passthrough.json")" = "bypassPermissions" ] \
    || fail "T40: dry-run changed the passthrough on disk"

printf '[T40b] a symlinked peer sidecar is part of the baseline and the union\n'
H40B=$(mk_home t40b)
run_al     "$H40B" "$META"  install >/dev/null
run_al_org "testpeer" "$H40B" "$META2" install >/dev/null
mv "$H40B/.cursor/.cli-config.testpeer-managed.json" "$TEST_DIR/t40b.peer.json"
ln -s "$TEST_DIR/t40b.peer.json" "$H40B/.cursor/.cli-config.testpeer-managed.json"
run_al "$H40B" "$META" install >/dev/null
if [ -f "$H40B/.cursor/.cli-config.user-managed.json" ] && grep -q 'npm' "$H40B/.cursor/.cli-config.user-managed.json"; then
    fail "T40b: the peer's rules were saved as user edits"
fi
[ "$(jq '.permissions.allow | index("Shell(npm:test)") != null' "$H40B/.cursor/cli-config.json")" = "true" ] \
    || fail "T40b: the peer's rules dropped out of the live file"

printf '[T40c] a meta that renders two JSON objects: nothing written\n'
H40C=$(mk_home t40c)
{ cat "$META"; cat "$META2"; } > "$TEST_DIR/meta/t40c.json"
rc=0
run_al "$H40C" "$TEST_DIR/meta/t40c.json" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T40c: install exited 0 on a two-object meta"
[ -z "$(find "$H40C/.claude" "$H40C/.cursor" -name '.*-managed.json' -print -quit)" ] || fail "T40c: a sidecar was written"

# ---------------------------------------------------------------------------
# T41 (r1.f9): the shipped personal.json names every MCP tool that may run;
# sends, shares, writes with no rollback, deletes and deploys prompt.
# ---------------------------------------------------------------------------
printf '[T41] real personal.json: no MCP server wildcard, no send/share/destructive tool auto-approved\n'
H41=$(mk_home t41)
REAL_META="$AGENTS_DIR/allowlists/personal.json"
run_al "$H41" "$REAL_META" install >/dev/null

# Every string each target would auto-approve, one per line.
rendered41() {
    jq -r '.terminalAllowlist[]' "$H41/.cursor/permissions.json"
    jq -r '.mcpAllowlist[]' "$H41/.cursor/permissions.json"
    jq -r '.permissions.allow[]' "$H41/.cursor/cli-config.json"
    jq -r '.permissions.allow[]' "$TEST_DIR/t41.claude.json"
}
claude_render "$REAL_META" > "$TEST_DIR/t41.claude.json"
rendered41 > "$TEST_DIR/t41.rendered"
cat "$H41/.gemini/policies/${ORG}-managed.toml" >> "$TEST_DIR/t41.rendered"

mcp_keys="notion slack miro-mcp firebase figma googledocs googleworkspace"
for k in $mcp_keys; do
    for form in "$k:*" "Mcp($k:*)" "mcp__${k}__*"; do
        if grep -qxF -- "$form" "$TEST_DIR/t41.rendered"; then
            fail "T41: server wildcard $form is auto-approved"
        fi
    done
    # The server still has named tools, so the key is not simply dropped.
    jq -e --arg k "$k" '.mcp.allow | map(select(startswith($k + ":"))) | length > 0' "$REAL_META" >/dev/null \
        || fail "T41: no named tool left for $k in personal.json"
done

# Sends, sharing and permission changes, and unrecoverable writes, by name.
for entry in \
    slack:slack_send_message slack:slack_schedule_message slack:slack_send_message_draft \
    googleworkspace:send_message googleworkspace:reply googleworkspace:forward \
    googleworkspace:share_file googleworkspace:create_event googleworkspace:trash_file \
    firebase:firestore_update_document firebase:firestore_delete_document \
    firebase:realtimedatabase_set_data firebase:firebase_deploy \
    firebase:messaging_send_message firebase:auth_update_user \
    miro-mcp:board_share miro-mcp:space_share miro-mcp:board_role_update miro-mcp:space_role_update \
    figma:generate_image figma:generate_vector_illustration \
    miro-mcp:section_delete \
    notion:notion-move-pages notion:notion-create-comment notion:notion-get-file-download-urls \
    figma:update_shader figma:weave_run_tool
do
    server=${entry%%:*}; tool=${entry#*:}
    for form in "$entry" "Mcp($entry)" "mcp__${server}__${tool}"; do
        if grep -qxF -- "$form" "$TEST_DIR/t41.rendered"; then
            fail "T41: $form is auto-approved"
        fi
    done
    if jq -e --arg e "$entry" '.mcp.allow | index($e)' "$REAL_META" >/dev/null; then
        fail "T41: $entry is in personal.json mcp.allow"
    fi
done

# r1.f4: no shell allow reads a secret or sends data (op read, op run, curl GET forms),
# in the meta and in each target, in the form that target writes:
#   Cursor IDE  terminalAllowlist  the bare entry
#   Cursor CLI  permissions.allow  Shell(<base>:<args>), split as the renderer splits it
#   Claude Code permissions.allow  Bash(<entry>), and the old prefix Bash(<entry>:*)
#               (the managed settings render)
#   Gemini      policy TOML        a `commandPrefix = "<entry>"` line
jq -r '.terminalAllowlist[]'  "$H41/.cursor/permissions.json" > "$TEST_DIR/t41.ide"
jq -r '.permissions.allow[]'  "$H41/.cursor/cli-config.json"  > "$TEST_DIR/t41.cli"
jq -r '.permissions.allow[]'  "$TEST_DIR/t41.claude.json"     > "$TEST_DIR/t41.claude"
cp "$H41/.gemini/policies/${ORG}-managed.toml"                  "$TEST_DIR/t41.gemini"
for removed in 'op read' 'op run' 'curl -X GET' 'curl --get' 'curl -G' 'wget --method=GET'; do
    if jq -e --arg e "$removed" '.shell.allow | index($e)' "$REAL_META" >/dev/null; then
        fail "T41: shell.allow still holds '$removed'"
    fi
    cli_form=$(jq -rn --arg e "$removed" '$e | capture("^(?<base>\\S+)\\s+(?<args>.+)$") | "Shell(" + .base + ":" + .args + ")"')
    gemini_line="commandPrefix = $(jq -rn --arg e "$removed" '$e | tojson')"
    grep -qxF -- "$removed"           "$TEST_DIR/t41.ide"    && fail "T41: '$removed' is in Cursor IDE terminalAllowlist"
    grep -qxF -- "$cli_form"          "$TEST_DIR/t41.cli"    && fail "T41: '$cli_form' is in Cursor CLI permissions.allow"
    grep -qxF -- "Bash($removed)"     "$TEST_DIR/t41.claude" && fail "T41: 'Bash($removed)' is in Claude Code permissions.allow"
    grep -qxF -- "Bash($removed:*)"   "$TEST_DIR/t41.claude" && fail "T41: 'Bash($removed:*)' is in Claude Code permissions.allow"
    grep -qxF -- "$gemini_line"       "$TEST_DIR/t41.gemini" && fail "T41: '$gemini_line' is in the Gemini policy"
done
# r1.f1: no shell allow from the real meta is a prefix in Claude Code or takes
# any arguments in Cursor CLI, so `git log --output=`, `rg --pre` or `make test
# x --eval=` still prompt there.
grep -E '^Bash\(.*(:\*| \*)\)$' "$TEST_DIR/t41.claude" && fail "T41: a Claude Code shell allow is a prefix rule"
grep -E '^Shell\([^:]*\)$'       "$TEST_DIR/t41.cli"    && fail "T41: a Cursor CLI shell allow takes any arguments"
for exact in 'Bash(git log)' 'Bash(rg)' 'Bash(git fetch)' 'Bash(make test)'; do
    grep -qxF -- "$exact" "$TEST_DIR/t41.claude" || fail "T41: Claude Code allow lacks the exact $exact"
done

# A named tool renders per tool in each target.
grep -qxF 'mcp__notion__notion-search'  "$TEST_DIR/t41.rendered" || fail "T41: mcp__notion__notion-search not rendered"
grep -qxF 'Mcp(notion:notion-search)'   "$TEST_DIR/t41.rendered" || fail "T41: Mcp(notion:notion-search) not rendered"
grep -qxF 'notion:notion-search'        "$TEST_DIR/t41.rendered" || fail "T41: notion:notion-search not rendered for Cursor IDE"
# Claude Code renders one rule per allowed MCP entry, none of them a wildcard.
n_meta=$(jq '.mcp.allow | length' "$REAL_META")
n_claude=$(jq '[.permissions.allow[] | select(startswith("mcp__"))] | length' "$TEST_DIR/t41.claude.json")
[ "$n_meta" = "$n_claude" ] || fail "T41: $n_meta meta mcp entries but $n_claude mcp__ rules in the Claude render"
[ "$(jq '[.permissions.allow[] | select(startswith("mcp__") and endswith("__*"))] | length' "$TEST_DIR/t41.claude.json")" = "0" ] \
    || fail "T41: a mcp__<server>__* wildcard is in the Claude render"

# The Cursor forms would pass these through as written; the managed settings
# render stops on them, so the install refuses the meta too.
printf '[T41b] a malformed mcp entry stops the render and writes nothing\n'
n=0
for bad in 'nocolon' ':tool' 'server:'; do
    n=$((n + 1))
    H41B=$(mk_home "t41b-$n")
    jq --arg b "$bad" '.mcp.allow += [$b]' "$META" > "$TEST_DIR/meta/t41b-$n.json"
    rc=0
    run_al "$H41B" "$TEST_DIR/meta/t41b-$n.json" install >/dev/null 2>&1 || rc=$?
    [ "$rc" -ne 0 ] || fail "T41b: install exited 0 on mcp entry '$bad'"
    [ -z "$(find "$H41B/.claude" "$H41B/.cursor" -name '.*-managed.json' -print -quit)" ] \
        || fail "T41b: a sidecar was written for mcp entry '$bad'"
    [ ! -f "$H41B/.claude/settings.json" ] || fail "T41b: settings.json written for mcp entry '$bad'"
done

# ---------------------------------------------------------------------------
# T42 (r1.f1): shell entries reach Cursor CLI and Claude Code wrapped, in the
# form each tool reads; Cursor IDE keeps the raw strings.
# ---------------------------------------------------------------------------
printf '[T42] shell forms: exact allows and prefix denies in Cursor CLI and Claude Code\n'
META42="$TEST_DIR/meta/t42.json"
cat > "$META42" <<'ENDJSON'
{
  "shell":    { "allow": ["git status", "pytest", "make test*", "ls ?", "./run:all now"],
                "deny":  ["git push --force", "sudo", "rm -rf /*", "rm -rf /", "rm -rf /?"] },
  "mcp":      { "allow": [], "deny": [] },
  "read":     { "deny": [] },
  "write":    { "deny": [] },
  "webfetch": { "allow": [], "deny": [] }
}
ENDJSON
H42=$(mk_home t42)
run_al "$H42" "$META42" install >/dev/null
CLI42="$H42/.cursor/cli-config.json"
CC42="$TEST_DIR/t42.claude.json"
claude_render "$META42" > "$CC42"
in_list() { jq -e --arg e "$3" ".permissions.$2 | index(\$e) != null" "$1" >/dev/null; }

# Cursor CLI allow: Shell(<base>:<args>) for a multi-word entry, nothing for a
# one-word entry (Shell(<word>) takes any arguments), a glob or a colon in the
# first word.
in_list "$CLI42" allow 'Shell(git:status)' || fail "T42: Cursor CLI multi-word allow is not Shell(git:status)"
in_list "$CLI42" allow 'Shell(pytest)' && fail "T42: Cursor CLI one-word allow Shell(pytest) takes any arguments"
[ "$(jq '.permissions.allow | length' "$CLI42")" = "1" ] \
    || fail "T42: Cursor CLI allow holds more than the one exact entry: $(jq -c '.permissions.allow' "$CLI42")"
for skipped in 'make test*' 'ls ?' './run:all now' 'Shell(make:test*)' 'Shell(ls:?)' 'Shell(./run:all now)' 'Shell(./run:all:now)'; do
    in_list "$CLI42" allow "$skipped" && fail "T42: Cursor CLI allow holds the unwritable entry $skipped"
done
# Cursor CLI deny: the prefix for a multi-word entry, Shell(<word>) for one
# word, a glob in the args as written.
in_list "$CLI42" deny 'Shell(git:push --force*)' || fail "T42: Cursor CLI multi-word deny is not the prefix Shell(git:push --force*)"
in_list "$CLI42" deny 'Shell(sudo)'              || fail "T42: Cursor CLI one-word deny is not Shell(sudo)"
in_list "$CLI42" deny 'Shell(rm:-rf /*)'         || fail "T42: Cursor CLI glob deny is not written as it is, Shell(rm:-rf /*)"
in_list "$CLI42" deny 'Shell(rm:-rf /**)' && fail "T42: Cursor CLI glob deny got a second *"
in_list "$CLI42" deny 'Shell(rm:-rf /?*)' || fail "T42: Cursor CLI deny with a ? is not a prefix, Shell(rm:-rf /?*)"
in_list "$CLI42" deny 'Shell(git:push --force)' && fail "T42: Cursor CLI deny is the exact form, which lets longer commands through"

# Claude Code: the exact Bash(<entry>) for an allow (none for a glob), the
# prefix Bash(<entry>:*) for a deny, a deny holding a * as it is.
in_list "$CC42" allow 'Bash(git status)'   || fail "T42: Claude Code multi-word allow is not the exact Bash(git status)"
in_list "$CC42" allow 'Bash(pytest)'       || fail "T42: Claude Code one-word allow is not the exact Bash(pytest)"
in_list "$CC42" allow 'Bash(./run:all now)' || fail "T42: Claude Code allow with a colon in the first word is not Bash(./run:all now)"
in_list "$CC42" allow 'Bash(make test*)'   && fail "T42: Claude Code glob allow was written; it would approve more than the entry"
[ "$(jq '[.permissions.allow[] | select(endswith(":*)") or endswith(" *)"))] | length' "$CC42")" = "0" ] \
    || fail "T42: Claude Code allow holds a prefix rule: $(jq -c '.permissions.allow' "$CC42")"
in_list "$CC42" deny 'Bash(git push --force:*)' || fail "T42: Claude Code multi-word deny is not Bash(git push --force:*)"
in_list "$CC42" deny 'Bash(sudo:*)'             || fail "T42: Claude Code one-word deny is not Bash(sudo:*)"
in_list "$CC42" deny 'Bash(rm -rf /*)'          || fail "T42: Claude Code glob deny is not written as it is, Bash(rm -rf /*)"
in_list "$CC42" deny 'Bash(rm -rf /:*)'         || fail "T42: Claude Code deny is not Bash(rm -rf /:*)"
for bad in 'Bash(rm -rf /*:*)' 'Bash(make test*:*)'; do
    in_list "$CC42" allow "$bad" && fail "T42: Claude Code allow holds $bad"
    in_list "$CC42" deny  "$bad" && fail "T42: Claude Code deny holds $bad"
done
# Neither file holds a bare string.
for f in "$CLI42" "$CC42"; do
    [ "$(jq '[.permissions.allow[], .permissions.deny[] | select(test("^[A-Za-z]+\\(") | not)] | length' "$f")" = "0" ] \
        || fail "T42: bare entry in $(basename "$f")"
done
# Cursor IDE keeps the raw strings.
[ "$(jq '.terminalAllowlist | index("git status") != null and index("pytest") != null' "$H42/.cursor/permissions.json")" = "true" ] \
    || fail "T42: Cursor IDE terminalAllowlist is not the raw entries"
[ "$(jq '.terminalDenylist | index("rm -rf /") != null and index("git push --force") != null' "$H42/.cursor/permissions.json")" = "true" ] \
    || fail "T42: Cursor IDE terminalDenylist is not the raw entries"

printf '[T42b] a Cursor CLI deny with a colon in its first word stops the render, nothing written\n'
H42B=$(mk_home t42b)
jq '.shell.deny += ["./run:all now"]' "$META42" > "$TEST_DIR/meta/t42b.json"
rc=0
run_al "$H42B" "$TEST_DIR/meta/t42b.json" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T42b: install exited 0 on an unwritable Cursor CLI deny"
[ -z "$(find "$H42B/.claude" "$H42B/.cursor" -name '.*-managed.json' -print -quit)" ] || fail "T42b: a sidecar was written"

printf '[T42c] stray whitespace in a shell entry neither drops nor breaks the rule, in any target\n'
META42C="$TEST_DIR/meta/t42c.json"
cat > "$META42C" <<'ENDJSON'
{
  "shell":    { "allow": ["  git   status "], "deny": [" sudo", "git push ", "rm  -rf /"] },
  "mcp":      { "allow": [], "deny": [] },
  "read":     { "deny": [] },
  "write":    { "deny": [] },
  "webfetch": { "allow": [], "deny": [] }
}
ENDJSON
H42C=$(mk_home t42c)
run_al "$H42C" "$META42C" install >/dev/null
for want in 'Shell(sudo)' 'Shell(git:push*)' 'Shell(rm:-rf /*)'; do
    in_list "$H42C/.cursor/cli-config.json" deny "$want" || fail "T42c: Cursor CLI deny lacks $want: $(jq -c '.permissions.deny' "$H42C/.cursor/cli-config.json")"
done
in_list "$H42C/.cursor/cli-config.json" allow 'Shell(git:status)' || fail "T42c: Cursor CLI allow lacks Shell(git:status)"
CC42C="$TEST_DIR/t42c.claude.json"
claude_render "$META42C" > "$CC42C"
for want in 'Bash(sudo:*)' 'Bash(git push:*)' 'Bash(rm -rf /:*)'; do
    in_list "$CC42C" deny "$want" || fail "T42c: Claude Code deny lacks $want: $(jq -c '.permissions.deny' "$CC42C")"
done
in_list "$CC42C" allow 'Bash(git status)' || fail "T42c: Claude Code allow lacks Bash(git status)"
[ "$(jq -c '.terminalDenylist' "$H42C/.cursor/permissions.json")" = '["git push","rm -rf /","sudo"]' ] \
    || fail "T42c: Cursor IDE terminalDenylist is not normalized: $(jq -c '.terminalDenylist' "$H42C/.cursor/permissions.json")"
[ "$(jq -c '.terminalAllowlist' "$H42C/.cursor/permissions.json")" = '["git status"]' ] \
    || fail "T42c: Cursor IDE terminalAllowlist is not normalized"
for want in 'commandPrefix = "sudo"' 'commandPrefix = "git push"' 'commandPrefix = "rm -rf /"' 'commandPrefix = "git status"'; do
    grep -qxF -- "$want" "$H42C/.gemini/policies/${ORG}-managed.toml" || fail "T42c: Gemini policy lacks $want"
done
H42D=$(mk_home t42d)
jq '.shell.deny += ["   "]' "$META42C" > "$TEST_DIR/meta/t42d.json"
rc=0
run_al "$H42D" "$TEST_DIR/meta/t42d.json" install >/dev/null 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "T42c: install exited 0 on an empty shell entry"

# ---------------------------------------------------------------------------
# T43 (r1.f1): upgrade from the previous render. The old installer wrote shell
# entries bare and every MCP entry as mcp__<server>__*; install replaces them
# with the wrapped forms in Cursor CLI, clears them from Claude Code's
# settings.json (the managed settings carry the rules now), and none is
# promoted to a user edit.
# ---------------------------------------------------------------------------
printf '[T43] upgrade from bare shell strings and mcp__<server>__* wildcards\n'
H43=$(mk_home t43)
META43="$TEST_DIR/meta/t43.json"
cat > "$META43" <<'ENDJSON'
{
  "shell":    { "allow": ["git status", "pytest"], "deny": ["rm -rf /", "sudo"] },
  "mcp":      { "allow": ["notion:notion-search", "slack:slack_read_channel"], "deny": [] },
  "read":     { "deny": [] },
  "write":    { "deny": [] },
  "webfetch": { "allow": ["docs.python.org"], "deny": [] }
}
ENDJSON
# What the previous installer rendered for the old meta (seven-style wildcards).
OLD_CLI='{"permissions":{"allow":["git status","pytest","Mcp(notion:*)","Mcp(slack:*)"],"deny":["rm -rf /","sudo"]}}'
OLD_CC='{"permissions":{"allow":["git status","pytest","mcp__notion__*","mcp__slack__*","WebFetch(domain:docs.python.org)"],"deny":["rm -rf /","sudo"]}}'
OLD_IDE='{"terminalAllowlist":["git status","pytest"],"terminalDenylist":["rm -rf /","sudo"],"mcpAllowlist":["notion:*","slack:*"],"mcpDenylist":[]}'
printf '%s\n' "$OLD_CLI" | jq -S . > "$H43/.cursor/cli-config.json"
printf '%s\n' "$OLD_CLI" | jq -S . > "$H43/.cursor/.cli-config.${ORG}-managed.json"
printf '%s\n' "$OLD_CC"  | jq -S . > "$H43/.claude/settings.json"
printf '%s\n' "$OLD_CC"  | jq -S . > "$H43/.claude/.settings.${ORG}-managed.json"
printf '%s\n' "$OLD_IDE" | jq -S . > "$H43/.cursor/permissions.json"
printf '%s\n' "$OLD_IDE" | jq -S . > "$H43/.cursor/.permissions.${ORG}-managed.json"
run_al "$H43" "$META43" install >/dev/null || fail "T43: install failed on the previous render"
CLI43="$H43/.cursor/cli-config.json"
[ "$(jq -c '.permissions.allow' "$CLI43")" = '["Mcp(notion:notion-search)","Mcp(slack:slack_read_channel)","Shell(git:status)"]' ] \
    || fail "T43: Cursor CLI allow after upgrade: $(jq -c '.permissions.allow' "$CLI43")"
[ "$(jq -c '.permissions.deny' "$CLI43")" = '["Shell(rm:-rf /*)","Shell(sudo)"]' ] \
    || fail "T43: Cursor CLI deny after upgrade: $(jq -c '.permissions.deny' "$CLI43")"
[ "$(jq '[.permissions.allow[], .permissions.deny[] | select(test("^[A-Za-z_]+(\\(|__)") | not)] | length' "$CLI43")" = "0" ] \
    || fail "T43: bare string left in cli-config.json permissions"
for old in 'Mcp(notion:*)' 'Mcp(slack:*)'; do
    jq -e --arg o "$old" '.permissions.allow | index($o) != null' "$CLI43" >/dev/null \
        && fail "T43: $old still in cli-config.json"
done
# settings.json only held the old render, so it goes, with every settings sidecar.
[ ! -e "$H43/.claude/settings.json" ] || fail "T43: settings.json kept: $(cat "$H43/.claude/settings.json")"
[ -z "$(find "$H43/.claude" -maxdepth 1 -name '.settings.*' -print -quit)" ] || fail "T43: a settings sidecar is left"
# Nothing was taken for the user's own.
[ ! -f "$H43/.cursor/.cli-config.user-managed.json" ] || fail "T43: the old render was promoted into .cli-config.user-managed.json"
[ ! -f "$H43/.claude/.settings.user-managed.json" ] || fail "T43: the old render was promoted into .settings.user-managed.json"
[ ! -f "$H43/.cursor/.permissions.user-managed.json" ] || fail "T43: the old render was promoted into .permissions.user-managed.json"
# The second install is a no-op: no further backup of either file (settings.json
# got one, on its way out).
n43=$(count_hist cli-config "$H43/.cursor"); m43=$(count_hist settings "$H43/.claude")
run_al "$H43" "$META43" install >/dev/null
[ "$(count_hist cli-config "$H43/.cursor")" = "$n43" ] && [ "$(count_hist settings "$H43/.claude")" = "$m43" ] \
    || fail "T43: a second install rewrote the files"
[ "$n43" = "1" ] && [ "$m43" = "1" ] || fail "T43: expected one backup of each live file, got cli-config=$n43 settings=$m43"

# ---------------------------------------------------------------------------
# T44: read.deny and write.deny reach Claude Code as Read() and Edit() denies
# ---------------------------------------------------------------------------
printf '[T44] read.deny and write.deny render as Claude Code Read() and Edit() denies\n'
META44="$TEST_DIR/meta/t44.json"
cat > "$META44" <<'ENDJSON'
{
  "shell":    { "allow": ["git status"], "deny": [] },
  "mcp":      { "allow": [], "deny": [] },
  "read":     { "deny": ["~/.ssh/**", "./.env"] },
  "write":    { "deny": ["/etc/**"] },
  "webfetch": { "allow": [], "deny": [] }
}
ENDJSON
CC44="$TEST_DIR/t44.claude.json"
claude_render "$META44" > "$CC44"
for rule in 'Read(~/.ssh/**)' 'Read(./.env)' 'Edit(/etc/**)'; do
    jq -e --arg r "$rule" '.permissions.deny | index($r) != null' "$CC44" >/dev/null \
        || fail "T44: $rule missing from Claude Code deny"
done
jq -e '.permissions.allow == ["Bash(git status)"]' "$CC44" >/dev/null \
    || fail "T44: Claude Code allow changed: $(jq -c '.permissions.allow' "$CC44")"

# ---------------------------------------------------------------------------
# T45: a file outside the format stops the install before anything is written
# ---------------------------------------------------------------------------
printf '[T45] unknown key, wrong list or empty entry stops the install, nothing written\n'
i45=0
for bad in '{"shell":{"allow":["ls"]},"shel":{"allow":["rm"]}}' \
           '{"read":{"allow":["~/x"]}}' \
           '{"shell":{"allow":"ls"}}' \
           '{"mcp":{"allow":[""]}}' \
           '{"webfetch":{"allow":["  "]}}'; do
    i45=$((i45 + 1))
    M45="$TEST_DIR/meta/t45-$i45.json"
    printf '%s\n' "$bad" > "$M45"
    H45=$(mk_home "t45-$i45")
    if run_al "$H45" "$M45" install >/dev/null 2>&1; then
        fail "T45: install accepted $bad"
    fi
    for f in "$H45/.cursor/permissions.json" "$H45/.cursor/cli-config.json" "$H45/.claude/settings.json"; do
        [ ! -f "$f" ] || fail "T45: $bad wrote $f"
    done
    find "$H45/.gemini" -name '*.toml' | grep -q . && fail "T45: $bad wrote a Gemini policy"
done

# ---------------------------------------------------------------------------
# Claude Code upgrade: clear what the previous installer rendered (m3)
# ---------------------------------------------------------------------------

# What the previous installer left in a Claude config dir: our sidecar (the
# claude_permissions render of the meta), an optional user-managed sidecar and
# passthrough, and settings.json, the passthrough merged over the union of
# every *-managed sidecar there (a peer org's included), keys sorted.
seed_old_claude() {
    local dir="$1" meta="$2" user="${3:-}" pt="${4:-}"
    mkdir -p "$dir"
    claude_render "$meta" > "$dir/.settings.${ORG}-managed.json"
    [ -z "$user" ] || printf '%s\n' "$user" | jq -S . > "$dir/.settings.user-managed.json"
    [ -z "$pt" ]   || printf '%s\n' "$pt"   | jq -S . > "$dir/.settings.passthrough.json"
    jq -s -S 'reduce .[] as $f ({permissions:{allow:[],deny:[]}};
        .permissions.allow = ((.permissions.allow + ($f.permissions.allow // [])) | unique) |
        .permissions.deny  = ((.permissions.deny  + ($f.permissions.deny  // [])) | unique))' \
        "$dir"/.settings.*-managed.json > "$dir/union.tmp"
    if [ -n "$pt" ]; then
        jq -s -S '.[0] * .[1]' "$dir/.settings.passthrough.json" "$dir/union.tmp" > "$dir/settings.json"
    else
        jq -S . "$dir/union.tmp" > "$dir/settings.json"
    fi
    rm -f "$dir/union.tmp"
}

snap_tree() { (cd "$1" && find . -print | LC_ALL=C sort | while IFS= read -r p; do
    if [ -f "$p" ]; then printf 'F %s %s\n' "$p" "$(cksum < "$p")"; else printf 'D %s\n' "$p"; fi
done); }

# ---------------------------------------------------------------------------
# T46: upgrade from a HOME the previous installer rendered. The user's own
# entries (promoted into user-managed, or added since and not yet promoted)
# and every other key stay, in order; ours go, a stale one included (the
# sidecar is the baseline, not the meta); the sidecars go; a second install is
# a no-op.
# ---------------------------------------------------------------------------
printf '[T46] upgrade: our Claude entries and sidecars go, the user'"'"'s stay\n'
H46=$(mk_home t46)
C46="$H46/.claude"
# The meta the previous install rendered held "old cmd", since dropped.
jq '.shell.allow += ["old cmd"]' "$META" > "$TEST_DIR/meta/t46-old.json"
seed_old_claude "$C46" "$TEST_DIR/meta/t46-old.json" \
    '{"permissions":{"allow":["Bash(mine)","Bash(git status)"],"deny":["Bash(curl:*)"]}}' \
    '{"model":"opus","permissions":{"defaultMode":"acceptEdits"}}'
# Added by hand after that install, never promoted.
jq '.permissions.allow += ["Bash(later)"]' "$C46/settings.json" > "$C46/s.tmp" && mv "$C46/s.tmp" "$C46/settings.json"
cp "$C46/settings.json" "$TEST_DIR/t46.before"
jq -e '.permissions.allow | index("Bash(old cmd)") != null and index("mcp__notion__*") != null' "$C46/settings.json" >/dev/null \
    || fail "T46: setup, the old render is not in settings.json"

snap_tree "$H46" > "$TEST_DIR/t46.tree.before"
out46=$(run_al "$H46" "$META" dry-run 2>&1) || fail "T46: dry-run failed: $out46"
snap_tree "$H46" > "$TEST_DIR/t46.tree.after"
cmp -s "$TEST_DIR/t46.tree.before" "$TEST_DIR/t46.tree.after" || fail "T46: dry-run changed $(basename "$H46")"
case "$out46" in *"settings.json"*"would remove"*"$ORG entries"*) ;; *) fail "T46: dry-run does not preview the removal: $out46" ;; esac
for sc in ".settings.${ORG}-managed.json" .settings.user-managed.json .settings.passthrough.json; do
    case "$out46" in *"would remove sidecar"*"$sc"*) ;; *) fail "T46: dry-run does not preview removing $sc" ;; esac
done
case "$(run_al "$H46" "$META" status 2>&1)" in *"settings.json"*"still holds $ORG entries"*) ;; *) fail "T46: status does not report the pending cleanup" ;; esac
diff46=$(run_al "$H46" "$META" diff 2>&1)
case "$diff46" in *'-      "mcp__notion__*",'*) ;; *) fail "T46: diff does not show our entries leaving: $diff46" ;; esac

run_al "$H46" "$META" install > "$TEST_DIR/t46.out" 2>&1 || fail "T46: install failed: $(cat "$TEST_DIR/t46.out")"
S46="$C46/settings.json"
[ "$(jq -c '.permissions.allow' "$S46")" = '["Bash(git status)","Bash(mine)","Bash(later)"]' ] \
    || fail "T46: allow after upgrade: $(jq -c '.permissions.allow' "$S46")"
[ "$(jq -c '.permissions.deny' "$S46")" = '["Bash(curl:*)"]' ] \
    || fail "T46: deny after upgrade: $(jq -c '.permissions.deny' "$S46")"
[ "$(jq -r '.model' "$S46")" = "opus" ] || fail "T46: model lost"
[ "$(jq -r '.permissions.defaultMode' "$S46")" = "acceptEdits" ] || fail "T46: defaultMode lost"
[ "$(jq -c 'keys_unsorted' "$S46")" = "$(jq -c 'keys_unsorted' "$TEST_DIR/t46.before")" ] || fail "T46: key order changed"
[ -z "$(find "$C46" -maxdepth 1 -name '.settings.*' -print -quit)" ] \
    || fail "T46: a settings sidecar is left: $(find "$C46" -maxdepth 1 -name '.settings.*')"
[ "$(count_hist settings "$C46")" = "1" ] || fail "T46: expected one backup of settings.json, got $(count_hist settings "$C46")"
cmp -s "$TEST_DIR/t46.before" "$C46/.history/settings.json.1" || fail "T46: the backup is not the pre-upgrade file"
grep -q "settings.json.*removed .* $ORG entries" "$TEST_DIR/t46.out" || fail "T46: install output does not report the removal"
# Second install: nothing to clear, nothing written, nothing said about it.
cp "$S46" "$TEST_DIR/t46.after1"
out46b=$(run_al "$H46" "$META" install 2>&1) || fail "T46: second install failed"
cmp -s "$TEST_DIR/t46.after1" "$S46" || fail "T46: second install changed settings.json"
[ "$(count_hist settings "$C46")" = "1" ] || fail "T46: second install backed settings.json up again"
case "$out46b" in *settings.json*) fail "T46: second install mentions settings.json: $out46b" ;; esac
case "$(run_al "$H46" "$META" status 2>&1)" in *settings.json*) fail "T46: status still reports settings.json after the upgrade" ;; esac

# ---------------------------------------------------------------------------
# T47: a settings.json that only held our render is removed (its backup kept);
# uninstall clears it too, and REMOVE_HISTORY=yes takes the backup with it.
# ---------------------------------------------------------------------------
printf '[T47] a settings.json of only our entries is removed, by install or uninstall\n'
H47=$(mk_home t47)
seed_old_claude "$H47/.claude" "$META"
run_al "$H47" "$META" install >/dev/null || fail "T47: install failed"
[ ! -e "$H47/.claude/settings.json" ] || fail "T47: settings.json kept: $(cat "$H47/.claude/settings.json")"
[ "$(ls -A "$H47/.claude")" = ".history" ] || fail "T47: .claude holds more than .history/: $(ls -A "$H47/.claude")"
[ -f "$H47/.claude/.history/settings.json.1" ] || fail "T47: no backup of the removed settings.json"

H47B=$(mk_home t47b)
run_al "$H47B" "$META" install >/dev/null
seed_old_claude "$H47B/.claude" "$META" '' '{"model":"opus"}'
REMOVE_HISTORY=yes run_al "$H47B" "$META" uninstall >/dev/null || fail "T47b: uninstall failed"
[ "$(cat "$H47B/.claude/settings.json" 2>/dev/null)" = "$(printf '{\n  "model": "opus"\n}')" ] \
    || fail "T47b: uninstall left settings.json as: $(cat "$H47B/.claude/settings.json" 2>&1)"
[ "$(ls -A "$H47B/.claude")" = "settings.json" ] || fail "T47b: uninstall left: $(ls -A "$H47B/.claude")"

# ---------------------------------------------------------------------------
# T48: another org's render is still in the file. Its entries stay, and so do
# entries both orgs wrote; the user-managed and passthrough sidecars stay for
# its installer; only our sidecar goes; lists are not tidied.
# ---------------------------------------------------------------------------
printf '[T48] a peer org still rendering settings.json keeps its entries and sidecars\n'
H48=$(mk_home t48)
C48="$H48/.claude"
mkdir -p "$C48"
# The peer also ships "git status".
jq '.shell.allow += ["git status"]' "$META2" > "$TEST_DIR/meta/t48-peer.json"
claude_render "$TEST_DIR/meta/t48-peer.json" > "$C48/.settings.testpeer-managed.json"
seed_old_claude "$C48" "$META" '{"permissions":{"allow":["Bash(mine)"],"deny":[]}}' '{"model":"opus"}'
cp "$C48/.settings.testpeer-managed.json" "$TEST_DIR/t48.peer"
run_al "$H48" "$META" install >/dev/null || fail "T48: install failed"
want48=$(jq -c '[.permissions.allow[]] + ["Bash(mine)"] | unique' "$TEST_DIR/t48.peer")
[ "$(jq -c '.permissions.allow | sort' "$C48/settings.json")" = "$want48" ] \
    || fail "T48: allow is $(jq -c '.permissions.allow' "$C48/settings.json"), want $want48"
[ "$(jq -c '.permissions.deny' "$C48/settings.json")" = '[]' ] || fail "T48: deny was tidied or kept ours: $(jq -c '.permissions.deny' "$C48/settings.json")"
[ ! -f "$C48/.settings.${ORG}-managed.json" ] || fail "T48: our sidecar is left"
cmp -s "$TEST_DIR/t48.peer" "$C48/.settings.testpeer-managed.json" || fail "T48: the peer's sidecar changed"
[ -f "$C48/.settings.user-managed.json" ] && [ -f "$C48/.settings.passthrough.json" ] \
    || fail "T48: user-managed or passthrough removed while the peer still renders"
# The peer's own installer (the previous version, still on that machine) would
# re-render the same file: the union of what is left.
jq -s -S '.[0] * {permissions:{allow:((.[1].permissions.allow + .[2].permissions.allow) | unique),
                               deny:((.[1].permissions.deny + .[2].permissions.deny) | unique)}}' \
    "$C48/.settings.passthrough.json" "$C48/.settings.testpeer-managed.json" "$C48/.settings.user-managed.json" \
    > "$TEST_DIR/t48.peer-render"
[ "$(jq -S -c . "$C48/settings.json")" = "$(jq -c . "$TEST_DIR/t48.peer-render")" ] \
    || fail "T48: settings.json is not what the peer's installer would render"

# ---------------------------------------------------------------------------
# T49: every listed Claude config dir and the Windows one are cleared; a dir
# with no sidecar of ours is left alone, byte for byte.
# ---------------------------------------------------------------------------
printf '[T49] every CLAUDE_CONFIG_DIRS dir and the Windows dir are cleared\n'
H49=$(mk_home t49)
W49=$(mk_win_home t49w)
seed_old_claude "$H49/.claude-a" "$META" '' '{"model":"a"}'
seed_old_claude "$H49/.claude-b" "$META" '' '{"model":"b"}'
seed_old_claude "$W49/.claude" "$META" '' '{"model":"w"}'
mkdir -p "$H49/.claude-c"
printf '{"permissions":{"allow":["Bash(git status)"]}}\n' > "$H49/.claude-c/settings.json"
cp "$H49/.claude-c/settings.json" "$TEST_DIR/t49.c"
ORG="$ORG" ALLOWLISTS_SRC="$META" CURSOR_DATA_HOME="$H49/.cursor" GEMINI_DATA_HOME="$H49/.gemini" \
CLAUDE_CONFIG_DIRS="$H49/.claude-a:$H49/.claude-b:$H49/.claude-c" \
WIN_HOME="$W49" WIN_CURSOR_DATA_HOME="$W49/.cursor" WIN_CLAUDE_DATA_HOME="$W49/.claude" WIN_GEMINI_DATA_HOME="$W49/.gemini" \
REMOVE_HISTORY=no bash "$ALLOWLISTS" install >/dev/null || fail "T49: install failed"
for d in "$H49/.claude-a:a" "$H49/.claude-b:b" "$W49/.claude:w"; do
    dir=${d%:*}; m=${d##*:}
    [ "$(jq -c . "$dir/settings.json")" = "{\"model\":\"$m\"}" ] || fail "T49: $dir/settings.json is $(jq -c . "$dir/settings.json")"
    [ -z "$(find "$dir" -maxdepth 1 -name '.settings.*' -print -quit)" ] || fail "T49: a sidecar is left in $dir"
done
cmp -s "$TEST_DIR/t49.c" "$H49/.claude-c/settings.json" || fail "T49: a dir with no sidecar of ours was changed"
[ ! -d "$H49/.claude-c/.history" ] || fail "T49: a dir with no sidecar of ours got a .history/"

# ---------------------------------------------------------------------------
# T50: clean removes the Claude config dirs' .history/ too, and restore no
# longer takes settings.json (a pre-upgrade backup would bring our entries
# back with no sidecar to clear them).
# ---------------------------------------------------------------------------
printf '[T50] clean covers the Claude .history/; restore refuses settings.json\n'
H50=$(mk_home t50)
seed_old_claude "$H50/.claude" "$META" '' '{"model":"opus"}'
run_al "$H50" "$META" install >/dev/null
[ -d "$H50/.claude/.history" ] || fail "T50: setup, no Claude .history/"
rc=0
RESTORE_N=1 RESTORE_FILE=settings.json run_al "$H50" "$META" restore >/dev/null 2>&1 || rc=$?
[ "$rc" -eq 2 ] || fail "T50: restore of settings.json exited $rc, want 2"
RESTORE_N=1 run_al "$H50" "$META" restore >/dev/null 2>&1
# install left settings.json as {"model":"opus"} (the passthrough key); a
# restore of every target must not put the pre-upgrade backup back over it.
[ "$(jq -c . "$H50/.claude/settings.json")" = '{"model":"opus"}' ] || fail "T50: restore replaced the cleared settings.json"
run_al "$H50" "$META" clean >/dev/null
[ ! -d "$H50/.claude/.history" ] || fail "T50: clean left the Claude .history/"
[ -f "$H50/.claude/settings.json" ] || fail "T50: clean removed settings.json"

# ---------------------------------------------------------------------------
# T51 (review): a link planted at .history/<file>.1 is replaced, not written
# through; status notes a foreign file in a Claude .history/; diff reports a
# pending cleanup when settings.json is gone but our sidecar is not.
# ---------------------------------------------------------------------------
printf '[T51] history links are not followed; Claude .history/ notes; diff with no settings.json\n'
H51=$(mk_home t51)
seed_old_claude "$H51/.claude" "$META" '' '{"model":"opus"}'
mkdir -p "$H51/.claude/.history"
printf 'precious\n' > "$TEST_DIR/t51.victim"
ln -s "$TEST_DIR/t51.victim" "$H51/.claude/.history/settings.json.1"
run_al "$H51" "$META" install >/dev/null || fail "T51: install failed"
[ "$(cat "$TEST_DIR/t51.victim")" = "precious" ] || fail "T51: the backup was written through a link at .history/settings.json.1"
[ -f "$H51/.claude/.history/settings.json.1" ] && [ ! -L "$H51/.claude/.history/settings.json.1" ] \
    || fail "T51: .history/settings.json.1 is not a regular backup"
printf 'x\n' > "$H51/.claude/.history/stray.txt"
case "$(run_al "$H51" "$META" status 2>&1)" in *"foreign"*"stray.txt"*) ;; *) fail "T51: status does not note a foreign file in the Claude .history/" ;; esac
H51B=$(mk_home t51b)
seed_old_claude "$H51B/.claude" "$META"
rm -f "$H51B/.claude/settings.json"
printf '{"permissions":{"allow":["Bash(mine)"],"deny":[]}}\n' > "$H51B/.claude/.settings.user-managed.json"
case "$(run_al "$H51B" "$META" diff 2>&1)" in *"settings.json ~ no file"*".settings.${ORG}-managed.json"*) ;; *) fail "T51: diff says nothing about the sidecar left with no settings.json" ;; esac
# With no settings.json the user-managed sidecar is the only copy of their rules.
run_al "$H51B" "$META" install >/dev/null || fail "T51: install failed with no settings.json"
[ ! -f "$H51B/.claude/.settings.${ORG}-managed.json" ] || fail "T51: our sidecar kept with no settings.json"
grep -q 'Bash(mine)' "$H51B/.claude/.settings.user-managed.json" 2>/dev/null || fail "T51: the user-managed sidecar was deleted with no settings.json"
# A directory link at a higher history slot doesn't take a backup.
H51C=$(mk_home t51c)
seed_old_claude "$H51C/.claude" "$META" '' '{"model":"opus"}'
mkdir -p "$H51C/.claude/.history" "$TEST_DIR/t51c.outside"
printf 'old\n' > "$H51C/.claude/.history/settings.json.1"
ln -s "$TEST_DIR/t51c.outside" "$H51C/.claude/.history/settings.json.2"
run_al "$H51C" "$META" install >/dev/null || fail "T51: install failed with a link at .history/settings.json.2"
[ -z "$(ls -A "$TEST_DIR/t51c.outside")" ] || fail "T51: a backup landed in the target of a .history link"
[ -f "$H51C/.claude/.history/settings.json.2" ] && [ ! -L "$H51C/.claude/.history/settings.json.2" ] \
    || fail "T51: .history/settings.json.2 is not the shifted backup"
# diff names a settings.json it can't read instead of saying nothing.
H51D=$(mk_home t51d)
seed_old_claude "$H51D/.claude" "$META"
printf '{"permissions":\n' > "$H51D/.claude/settings.json"
case "$(run_al "$H51D" "$META" diff 2>/dev/null)" in *"settings.json ! cannot compute"*) ;; *) fail "T51: diff is silent on a settings.json it can't read" ;; esac

# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------
if [ "$FAILED" -eq 0 ]; then
    printf '\nAll tests passed.\n'
else
    printf '\n%d test(s) FAILED.\n' "$FAILED" >&2
    exit 1
fi
