#!/usr/bin/env bash
# Installer for the Cursor user-level hooks this installer owns:
#
#   refresh   ~/.cursor/hooks/$ORG-refresh-skills.sh on sessionStart and
#             afterFileEdit. Re-copies copy-mode Cursor skills after edits
#             under this repo's plugins/. Only needed while CURSOR_SKILLS_MODE=copy; in plugin or
#             symlink mode install removes it.
#   denylist  ~/.cursor/hooks/$ORG-enforce-denylist.sh on
#             beforeShellExecution (failClosed) and preToolUse. The Cursor IDE
#             ignores terminalDenylist, so this hook enforces the deny entries
#             that allowlists.sh renders into ~/.cursor/permissions.json. It
#             belongs with the allowlists, so it's installed in every mode.
#
# hooks.json is always merged, never overwritten: entries from other
# installers or added by hand survive every operation. The wrappers are pure
# bash at runtime; python3 is used only to edit hooks.json.
#
# Required env (set by the calling Makefile):
#   ORG, AGENTS_DIR, SKILLS_SRC, COMMANDS_SRC
#
# Optional env:
#   CURSOR_DATA_HOME     (default: $HOME/.cursor)
#   CURSOR_SKILLS_SRC    Cursor-only skill dirs, passed to the refresh
#   CURSOR_SKILLS_MODE   copy | symlink | plugin (default: copy)
#   DENYLIST_HOOK_SRC    source of the denylist hook
#                        (default: $AGENTS_DIR/cursor/hooks/enforce-denylist.sh)
#   PLUGINS_DIR          repo plugins dir; afterFileEdit under it triggers a refresh
#
# Subcommands:
#   install      Write the wrappers + hooks.json entries (refresh per mode).
#   uninstall    Remove our wrappers, hooks.json entries, and refresh log.
#   dry-run      Preview install actions; no disk writes.
#   status       Report hook installation state; no writes.

set -euo pipefail

: "${ORG:?ORG must be set}"
: "${AGENTS_DIR:?AGENTS_DIR must be set}"
: "${SKILLS_SRC:?SKILLS_SRC must be set}"
: "${COMMANDS_SRC:?COMMANDS_SRC must be set}"
: "${CURSOR_DATA_HOME:=$HOME/.cursor}"
: "${CURSOR_SKILLS_SRC:=}"
: "${CURSOR_SKILLS_MODE:=copy}"
: "${DENYLIST_HOOK_SRC:=$AGENTS_DIR/cursor/hooks/enforce-denylist.sh}"
: "${PLUGINS_DIR:=$(dirname "$AGENTS_DIR")/plugins}"

EXTENSIONS_SH="$AGENTS_DIR/lib/extensions.sh"
HOOKS_DIR="$CURSOR_DATA_HOME/hooks"
HOOK_SCRIPT="$HOOKS_DIR/${ORG}-refresh-skills.sh"
DENY_SCRIPT="$HOOKS_DIR/${ORG}-enforce-denylist.sh"
LEGACY_DENY_SCRIPT="$HOOKS_DIR/enforce-denylist.sh"
HOOKS_JSON="$CURSOR_DATA_HOME/hooks.json"
HOOKS_MARKER="$CURSOR_DATA_HOME/hooks.json.${ORG}-managed"
HOOK_COMMAND="./hooks/${ORG}-refresh-skills.sh"
DENY_COMMAND="./hooks/${ORG}-enforce-denylist.sh"
LEGACY_DENY_COMMAND="./hooks/enforce-denylist.sh"
REFRESH_LOG="$CURSOR_DATA_HOME/${ORG}-refresh.log"
REFRESH_LOCK="$CURSOR_DATA_HOME/.${ORG}-refresh.lock"

DRY_RUN=0

pretty_path() {
    local p="$1"
    case "$p" in
        "$HOME"/*) printf '~/%s' "${p#"$HOME"/}" ;;
        *)         printf '%s' "$p" ;;
    esac
}

refresh_wanted() {
    [ "$CURSOR_SKILLS_MODE" = "copy" ]
}

write_hook_script() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s + would write refresh hook script\n' "$(pretty_path "$HOOK_SCRIPT")"
        return 0
    fi

    mkdir -p -- "$HOOKS_DIR"
    cat > "$HOOK_SCRIPT" <<EOF
#!/usr/bin/env bash
# Auto-refresh copy-mode Cursor skills after skill/command edits.
# Managed by the $ORG agents installer — do not edit by hand.
set -euo pipefail

SKILLS_SRC='$SKILLS_SRC'
CURSOR_SKILLS_SRC='$CURSOR_SKILLS_SRC'
COMMANDS_SRC='$COMMANDS_SRC'
PLUGINS_DIR='$PLUGINS_DIR'
EXTENSIONS_SH='$EXTENSIONS_SH'
ORG='$ORG'
AGENTS_DIR='$AGENTS_DIR'
LOG='$REFRESH_LOG'
LOCK='$REFRESH_LOCK'

if [ "\${1:-}" = "--refresh-inner" ]; then
    ORG="\$ORG" \\
    SKILLS_SRC="\$SKILLS_SRC" \\
    CURSOR_SKILLS_SRC="\$CURSOR_SKILLS_SRC" \\
    COMMANDS_SRC="\$COMMANDS_SRC" \\
    AGENTS_DIR="\$AGENTS_DIR" \\
    CURSOR_SKILLS_MODE=copy \\
    CURSOR_SKILLS_HOME="\$HOME/.cursor/skills" \\
    bash "\$EXTENSIONS_SH" refresh >> "\$LOG" 2>&1 || true
    exit 0
fi

payload=\$(cat)

# Refresh on session start, and after an edit under the repo's plugins/.
# Other edits don't touch skill sources, so skip them.
should_refresh=1
case "\$payload" in
    *afterFileEdit*)
        case "\$payload" in
            *"\$PLUGINS_DIR"*) ;;
            *) should_refresh=0 ;;
        esac
        ;;
esac

[ "\$should_refresh" -eq 1 ] || exit 0

if command -v flock >/dev/null 2>&1; then
    flock -n "\$LOCK" bash "\$0" --refresh-inner || true
else
    bash "\$0" --refresh-inner || true
fi
exit 0
EOF
    # No `--`: macOS / BSD chmod treats it as a filename (GNU chmod accepts it).
    chmod 0755 "$HOOK_SCRIPT"
    printf '%-50s + wrote refresh hook script\n' "$(pretty_path "$HOOK_SCRIPT")"
}

# Copy (not symlink) the denylist hook: it runs failClosed, so a symlink into
# a checkout that moves or disappears would block every Shell call.
write_deny_script() {
    if [ ! -f "$DENYLIST_HOOK_SRC" ]; then
        printf 'note: %s missing; skipping denylist hook\n' "$(pretty_path "$DENYLIST_HOOK_SRC")" >&2
        return 0
    fi
    if [ -f "$DENY_SCRIPT" ] && cmp -s "$DENYLIST_HOOK_SRC" "$DENY_SCRIPT"; then
        printf '%-50s = denylist hook current\n' "$(pretty_path "$DENY_SCRIPT")"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s + would write denylist hook\n' "$(pretty_path "$DENY_SCRIPT")"
        return 0
    fi
    mkdir -p -- "$HOOKS_DIR"
    cp "$DENYLIST_HOOK_SRC" "$DENY_SCRIPT"
    chmod 0755 "$DENY_SCRIPT"
    printf '%-50s + wrote denylist hook\n' "$(pretty_path "$DENY_SCRIPT")"
}

# The README used to say to link enforce-denylist.sh by hand. Adopt that
# copy when it's ours: a link into an installer checkout, or identical to the source.
legacy_deny_is_ours() {
    [ -e "$LEGACY_DENY_SCRIPT" ] || [ -L "$LEGACY_DENY_SCRIPT" ] || return 1
    if [ -L "$LEGACY_DENY_SCRIPT" ]; then
        case "$(readlink "$LEGACY_DENY_SCRIPT")" in
            */cursor/hooks/enforce-denylist.sh) return 0 ;;
        esac
    fi
    [ -f "$DENYLIST_HOOK_SRC" ] && cmp -s "$DENYLIST_HOOK_SRC" "$LEGACY_DENY_SCRIPT"
}

remove_file() {
    local path="$1" what="$2"
    [ -e "$path" ] || [ -L "$path" ] || return 0
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s - would remove %s\n' "$(pretty_path "$path")" "$what"
        return 0
    fi
    rm -f -- "$path"
    printf '%-50s - removed %s\n' "$(pretty_path "$path")" "$what"
}

# Merge our entries into hooks.json. $1 = refresh on|off, $2 = deny on|off,
# $3 = adopt the hand-installed denylist entry yes|no. Creates the file (and
# our marker) when missing; on removal deletes it only if we created it and
# nothing else is left.
edit_hooks_json() {
    local refresh="$1" deny="$2" adopt="$3"
    if [ ! -f "$HOOKS_JSON" ] && [ "$refresh" = "off" ] && [ "$deny" = "off" ]; then
        rm -f -- "$HOOKS_MARKER"
        return 0
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        printf 'error: python3 is required to edit %s safely\n' "$(pretty_path "$HOOKS_JSON")" >&2
        return 1
    fi
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s ~ would update hooks.json (refresh %s, denylist %s)\n' \
            "$(pretty_path "$HOOKS_JSON")" "$refresh" "$deny"
        return 0
    fi
    mkdir -p -- "$CURSOR_DATA_HOME"
    [ -f "$HOOKS_JSON" ] || : > "$HOOKS_MARKER"
    local result
    result=$(python3 - "$HOOKS_JSON" "$refresh" "$deny" "$adopt" \
        "$HOOK_COMMAND" "$DENY_COMMAND" "$LEGACY_DENY_COMMAND" <<'PY'
import json, os, sys

path, refresh, deny, adopt, refresh_cmd, deny_cmd, legacy_cmd = sys.argv[1:8]
data = {}
if os.path.exists(path) and os.path.getsize(path) > 0:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
before = json.dumps(data, sort_keys=True)
data.setdefault("version", 1)
hooks = data.setdefault("hooks", {})

def ours(entry, cmd):
    return isinstance(entry, dict) and entry.get("command") == cmd

def drop(cmd):
    for event in list(hooks):
        items = hooks[event]
        if isinstance(items, list):
            items[:] = [h for h in items if not ours(h, cmd)]
            if not items:
                del hooks[event]

def add(event, entry):
    items = hooks.setdefault(event, [])
    if not any(ours(h, entry["command"]) for h in items):
        items.append(entry)

drop(refresh_cmd)
if refresh == "on":
    add("sessionStart", {"command": refresh_cmd})
    add("afterFileEdit", {"command": refresh_cmd})
if adopt == "yes":
    drop(legacy_cmd)
drop(deny_cmd)
if deny == "on":
    add("beforeShellExecution", {"command": deny_cmd, "failClosed": True})
    add("preToolUse", {"command": deny_cmd})
if not hooks:
    data.pop("hooks", None)

if set(data) <= {"version"}:
    print("empty")
else:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print("changed" if json.dumps(data, sort_keys=True) != before else "same")
PY
)
    case "$result" in
        empty)
            if [ -f "$HOOKS_MARKER" ]; then
                rm -f -- "$HOOKS_JSON" "$HOOKS_MARKER"
                printf '%-50s - removed hooks.json (we created it; now empty)\n' "$(pretty_path "$HOOKS_JSON")"
            else
                printf '{\n  "version": 1\n}\n' > "$HOOKS_JSON"
                printf '%-50s ~ removed our hooks.json entries\n' "$(pretty_path "$HOOKS_JSON")"
            fi
            ;;
        changed) printf '%-50s ~ updated hooks.json (refresh %s, denylist %s)\n' "$(pretty_path "$HOOKS_JSON")" "$refresh" "$deny" ;;
        same)    printf '%-50s = hooks.json current\n' "$(pretty_path "$HOOKS_JSON")" ;;
    esac
}

run_install() {
    local refresh=off adopt=no deny=on
    if refresh_wanted; then
        refresh=on
        write_hook_script
    else
        remove_file "$HOOK_SCRIPT" "refresh hook script (cursor skills: $CURSOR_SKILLS_MODE)"
    fi
    [ -f "$DENYLIST_HOOK_SRC" ] || deny=off
    write_deny_script
    if legacy_deny_is_ours; then
        adopt=yes
        remove_file "$LEGACY_DENY_SCRIPT" "hand-installed denylist hook (now $(basename "$DENY_SCRIPT"))"
    fi
    edit_hooks_json "$refresh" "$deny" "$adopt"
}

cmd_install() {
    DRY_RUN=0
    printf 'install-hooks: org=%s, agents=%s, cursor skills=%s\n' \
        "$ORG" "$(pretty_path "$AGENTS_DIR")" "$CURSOR_SKILLS_MODE"
    run_install
}

cmd_uninstall() {
    DRY_RUN=0
    printf 'uninstall-hooks: org=%s\n' "$ORG"
    local adopt=no
    legacy_deny_is_ours && adopt=yes
    edit_hooks_json off off "$adopt"
    remove_file "$HOOK_SCRIPT" "refresh hook script"
    remove_file "$DENY_SCRIPT" "denylist hook"
    if [ "$adopt" = "yes" ]; then
        remove_file "$LEGACY_DENY_SCRIPT" "hand-installed denylist hook"
    fi
    remove_file "$REFRESH_LOG" "refresh log"
    remove_file "$REFRESH_LOCK" "refresh lock"
    rmdir "$HOOKS_DIR" 2>/dev/null || true
}

cmd_dry_run() {
    DRY_RUN=1
    printf 'dry-run-hooks: org=%s, agents=%s, cursor skills=%s\n' \
        "$ORG" "$(pretty_path "$AGENTS_DIR")" "$CURSOR_SKILLS_MODE"
    run_install
}

report_script() {
    local path="$1" what="$2" wanted="$3"
    if [ -x "$path" ]; then
        printf '%-50s = %s present\n' "$(pretty_path "$path")" "$what"
    elif [ -f "$path" ]; then
        printf '%-50s ~ %s present (not executable)\n' "$(pretty_path "$path")" "$what"
    elif [ "$wanted" = "yes" ]; then
        printf '%-50s + %s missing\n' "$(pretty_path "$path")" "$what"
    else
        printf '%-50s = %s not used (cursor skills: %s)\n' "$(pretty_path "$path")" "$what" "$CURSOR_SKILLS_MODE"
    fi
}

cmd_status() {
    printf 'status-hooks: org=%s\n' "$ORG"
    local wanted=no
    if refresh_wanted; then wanted=yes; fi
    report_script "$HOOK_SCRIPT" "refresh hook" "$wanted"
    report_script "$DENY_SCRIPT" "denylist hook" yes
    if [ ! -f "$HOOKS_JSON" ]; then
        printf '%-50s + missing\n' "$(pretty_path "$HOOKS_JSON")"
        return 0
    fi
    if grep -qF "$HOOK_COMMAND" "$HOOKS_JSON" 2>/dev/null; then
        printf '%-50s = refresh registered\n' "$(pretty_path "$HOOKS_JSON")"
    fi
    if grep -qF "$DENY_COMMAND" "$HOOKS_JSON" 2>/dev/null; then
        printf '%-50s = denylist registered\n' "$(pretty_path "$HOOKS_JSON")"
    else
        printf '%-50s + denylist not registered\n' "$(pretty_path "$HOOKS_JSON")"
    fi
}

usage() {
    cat <<EOF
usage: $0 {install|uninstall|dry-run|status}

Installs the Cursor user hooks this installer owns (skill refresh, denylist).
Invoked by the agents Makefile.
EOF
}

case "${1:-}" in
    install)    cmd_install ;;
    uninstall)  cmd_uninstall ;;
    dry-run)    cmd_dry_run ;;
    status)     cmd_status ;;
    -h|--help|help|"") usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
