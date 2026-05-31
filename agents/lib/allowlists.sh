#!/usr/bin/env bash
# Installer for agent allowlists: renders one tool-agnostic meta-source JSON
# into three tool-specific config files:
#
#   ~/.cursor/permissions.json     (Cursor IDE)
#   ~/.cursor/cli-config.json      (Cursor CLI)
#   ~/.claude/settings.json        (Claude Code / VS Code + Cursor extension)
#
# When running under WSL, the same three files are also rendered into the
# Windows host home (%USERPROFILE%) so that native (non-WSL) Cursor and
# Claude Code can read them. Each Windows-side target gets its own sidecars,
# .history/ backups, user-edit promotion, and guardrail — identical to the
# Unix-side targets and completely independent.
#
# Coexistence is handled by per-org sidecars (.<stem>.<org>-managed.json):
# each installer (agerpoint, personal, ...) writes its own sidecar, the
# renderer unions all of them plus the engineer's own auto-promoted entries
# (.<stem>.user-managed.json) and passthrough keys (.<stem>.passthrough.json).
#
# Backups live in a hidden .history/ subdirectory next to each live file
# (~/.cursor/.history/permissions.json.1, .2, ... and ~/.claude/.history/
# settings.json.1, .2, ...). Numbering is unbounded and per-file; engineer
# prunes manually or via `make clean-allowlists`.
#
# Required env (set by the calling Makefile):
#   ORG               installer identity ("agerpoint", "personal", ...)
#   ALLOWLISTS_SRC    absolute path to the tool-agnostic meta-source JSON
#
# Optional env (defaults shown):
#   CURSOR_DATA_HOME      ~/.cursor
#   CLAUDE_DATA_HOME      ~/.claude
#   WIN_HOME              (empty; auto-detected when /proc/version contains
#                         "microsoft" — the WSL Windows host home directory)
#   WIN_CURSOR_DATA_HOME  $WIN_HOME/.cursor   (derived from WIN_HOME)
#   WIN_CLAUDE_DATA_HOME  $WIN_HOME/.claude   (derived from WIN_HOME)
#   MAKEFILE_LABEL        parent-of-ALLOWLISTS_SRC/Makefile
#   RESTORE_N             (restore subcommand) which .history/<file>.<N> to restore
#   RESTORE_FILE          (restore subcommand) restrict to one of:
#                         permissions.json | cli-config.json | settings.json
#                         (default: restore every target that has a matching .N)
#   REMOVE_HISTORY        (uninstall subcommand) skip the interactive prompt:
#                         yes/1 -> remove .history/, no/0 -> keep it. Unset ->
#                         prompt (default KEEP), or auto-keep on a non-TTY stdin.
#
# Requires: jq (any modern version; tested with 1.6+).
#
# Subcommands:
#   install      Render all targets atomically (Unix + Windows if WSL).
#                Rotates .history/<file>.N only when bytes change.
#                Idempotent: a second run is a no-op.
#   uninstall    Remove this $ORG's sidecar from each target and re-render
#                (which removes our entries while preserving other orgs',
#                user-managed entries, and passthrough keys). On success,
#                offers to remove .history/ (inline prompt on /dev/tty,
#                default KEEP). Honors $REMOVE_HISTORY to skip the prompt;
#                with no usable terminal the prompt is skipped and .history/
#                is kept.
#   dry-run      Same as install but no disk writes.
#   status       Per-target report; flags foreign files inside .history/.
#   diff         Show diff between expected (re-render) and live for each target.
#   restore      Copy .history/<stem>.json.<RESTORE_N> back over the live file
#                for all targets (Unix + Windows) whose .N exists. RESTORE_FILE
#                restricts to one stem, keeping both sides consistent.
#   clean        Remove .history/ subdirectories entirely (explicit nuke knob).

set -euo pipefail

# ---------------------------------------------------------------------------
# Required + optional env
# ---------------------------------------------------------------------------

: "${ORG:?ORG must be set}"
: "${ALLOWLISTS_SRC:?ALLOWLISTS_SRC must be set}"
: "${CURSOR_DATA_HOME:=$HOME/.cursor}"
: "${CLAUDE_DATA_HOME:=$HOME/.claude}"
: "${MAKEFILE_LABEL:=${ALLOWLISTS_SRC%/*}/Makefile}"

# Windows-host vars (populated by init_win_home / init_win_dests at runtime)
: "${WIN_HOME:=}"
: "${WIN_CURSOR_DATA_HOME:=}"
: "${WIN_CLAUDE_DATA_HOME:=}"

: "${RESTORE_N:=}"
: "${RESTORE_FILE:=}"
: "${REMOVE_HISTORY:=}"

command -v jq >/dev/null 2>&1 || {
    printf 'error: jq is required by %s (install via your package manager)\n' \
        "$(basename -- "$0")" >&2
    exit 2
}

LOCK_FILE="$CURSOR_DATA_HOME/.allowlists.lock"
LOCK_DIR="$LOCK_FILE.d"
LOCK_ACQUIRED=0

DRY_RUN=0
MODE="install"            # install | uninstall | dry-run | status | diff | restore | clean
ABORTED=0

# Cross-target accumulators printed at the end of every run.
CONFLICTS=()
NOTES=()

# ---------------------------------------------------------------------------
# WSL / Windows-host detection (mirrors extensions.sh)
# ---------------------------------------------------------------------------

is_wsl() {
    [ -r /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null
}

detect_win_home() {
    is_wsl || return 1
    command -v cmd.exe  >/dev/null 2>&1 || return 1
    command -v wslpath  >/dev/null 2>&1 || return 1

    local userprofile wsl_path
    userprofile=$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' || true)
    [ -n "$userprofile" ] || return 1

    wsl_path=$(wslpath "$userprofile" 2>/dev/null || true)
    [ -n "$wsl_path" ] && [ -d "$wsl_path" ] || return 1

    printf '%s' "$wsl_path"
}

# Populate $WIN_HOME when running under WSL and it isn't already set.
init_win_home() {
    [ -n "$WIN_HOME" ] && return 0
    is_wsl || return 0
    local detected
    if detected=$(detect_win_home 2>/dev/null); then
        WIN_HOME="$detected"
    else
        printf 'note: WSL detected but Windows host home could not be resolved\n' >&2
        printf '      (cmd.exe interop or wslpath unavailable; Windows-native\n' >&2
        printf '      tools will not see the allowlists until this is fixed)\n' >&2
    fi
}

# Derive WIN_CURSOR_DATA_HOME / WIN_CLAUDE_DATA_HOME from WIN_HOME.
# Safe to call repeatedly; only sets vars that are empty.
init_win_dests() {
    [ -n "$WIN_HOME" ] || return 0
    : "${WIN_CURSOR_DATA_HOME:=$WIN_HOME/.cursor}"
    : "${WIN_CLAUDE_DATA_HOME:=$WIN_HOME/.claude}"
}

# ---------------------------------------------------------------------------
# Target table
# ---------------------------------------------------------------------------
# Each line: <stem>|<dir>|<kind>
#   stem = filename without .json (e.g. "permissions")
#   dir  = parent directory containing the live file and sidecars
#   kind = cursor_ide | cursor_cli | claude  (drives schema translation)

all_targets() {
    printf '%s\n' \
        "permissions|$CURSOR_DATA_HOME|cursor_ide" \
        "cli-config|$CURSOR_DATA_HOME|cursor_cli" \
        "settings|$CLAUDE_DATA_HOME|claude"
    [ -n "$WIN_HOME" ] && printf '%s\n' \
        "permissions|$WIN_CURSOR_DATA_HOME|cursor_ide" \
        "cli-config|$WIN_CURSOR_DATA_HOME|cursor_cli" \
        "settings|$WIN_CLAUDE_DATA_HOME|claude"
}

# Stems-per-directory map, used by foreign-history detection so each
# .history/ dir only flags files that don't belong to any installed target
# under its parent directory.
stems_in_dir() {
    local target_dir="$1"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        [ "$dir" = "$target_dir" ] || continue
        printf '%s\n' "$stem"
    done < <(all_targets)
}

# ---------------------------------------------------------------------------
# Pretty-print path: $HOME -> ~, %USERPROFILE% -> %USERPROFILE%/...
# ---------------------------------------------------------------------------

pretty_path() {
    local p="$1"
    case "$p" in
        "$HOME"/*) printf '~/%s' "${p#"$HOME"/}" ;;
        *)
            if [ -n "$WIN_HOME" ]; then
                case "$p" in
                    "$WIN_HOME"/*) printf '%%USERPROFILE%%/%s' "${p#"$WIN_HOME"/}" ; return ;;
                    "$WIN_HOME")   printf '%%USERPROFILE%%'                         ; return ;;
                esac
            fi
            printf '%s' "$p"
            ;;
    esac
}

# Returns " [win]" when $dir is under WIN_HOME, else "".
# Append to printf format strings for dual-pass output disambiguation.
side_label() {
    local dir="$1"
    [ -n "$WIN_HOME" ] || return 0
    case "$dir" in
        "$WIN_HOME"/*|"$WIN_HOME") printf ' [win]' ;;
    esac
}

# ---------------------------------------------------------------------------
# Portable advisory lock (mkdir-based; works without flock on macOS).
# ---------------------------------------------------------------------------

release_lock() {
    if [ "$LOCK_ACQUIRED" = "1" ]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
        LOCK_ACQUIRED=0
    fi
}

acquire_lock() {
    mkdir -p "$(dirname "$LOCK_FILE")"
    local tries=0
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        tries=$((tries + 1))
        if [ "$tries" -gt 600 ]; then       # ~30 s at 50 ms per spin
            printf 'error: timed out acquiring lock at %s\n' "$LOCK_DIR" >&2
            printf '       remove the lockdir manually if no other run is in progress\n' >&2
            exit 1
        fi
        sleep 0.05
    done
    LOCK_ACQUIRED=1
    trap release_lock EXIT INT TERM
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

target_path()     { printf '%s/%s.json'                "$2" "$1"; }   # stem dir
org_sidecar()     { printf '%s/.%s.%s-managed.json'    "$2" "$1" "$ORG"; }
user_sidecar()    { printf '%s/.%s.user-managed.json'  "$2" "$1"; }
passthrough_path(){ printf '%s/.%s.passthrough.json'   "$2" "$1"; }
history_dir_of()  { printf '%s/.history'               "$1"; }
history_file()    { printf '%s/.history/%s.json.%s'    "$2" "$1" "$3"; } # stem dir n

# ---------------------------------------------------------------------------
# Schema translation: meta-source JSON -> tool-specific shape
# ---------------------------------------------------------------------------
# kind = cursor_ide | cursor_cli | claude
# Output is canonical (sorted keys, deduped + sorted arrays via `unique`) so
# the diff between two renders of the same inputs is byte-identical.

render_target_schema() {
    local kind="$1" meta="$2"
    case "$kind" in
        cursor_ide)
            jq -S '{
                terminalAllowlist: ((.shell.allow    // []) | unique),
                terminalDenylist:  ((.shell.deny     // []) | unique),
                mcpAllowlist:      ((.mcp.allow      // []) | unique),
                mcpDenylist:       ((.mcp.deny       // []) | unique)
            }' "$meta"
            ;;
        cursor_cli)
            jq -S '{
                permissions: {
                    allow: (
                        ((.shell.allow // []) +
                         ((.mcp.allow  // []) | map("Mcp(" + . + ")"))
                        ) | unique
                    ),
                    deny: (
                        ((.shell.deny // []) +
                         ((.mcp.deny  // []) | map("Mcp(" + . + ")"))
                        ) | unique
                    )
                }
            }' "$meta"
            ;;
        claude)
            jq -S '{
                permissions: {
                    allow: (
                        ((.shell.allow    // []) +
                         ((.mcp.allow     // []) | map("mcp__" + (split(":")[0]) + "__*")) +
                         ((.webfetch.allow // []) | map("WebFetch(domain:" + . + ")"))
                        ) | unique
                    ),
                    deny: (
                        ((.shell.deny    // []) +
                         ((.mcp.deny     // []) | map("mcp__" + (split(":")[0]) + "__*")) +
                         ((.webfetch.deny // []) | map("WebFetch(domain:" + . + ")"))
                        ) | unique
                    )
                }
            }' "$meta"
            ;;
        *)
            printf 'render_target_schema: unknown kind %s\n' "$kind" >&2
            return 2
            ;;
    esac
}

# Union N JSON files that are already in the target schema. Permission
# arrays are concatenated then `unique`d so order is deterministic.
union_target_schema() {
    local kind="$1"; shift
    case "$kind" in
        cursor_ide)
            jq -s -S 'reduce .[] as $f ({};
                .terminalAllowlist = (((.terminalAllowlist // []) + ($f.terminalAllowlist // [])) | unique) |
                .terminalDenylist  = (((.terminalDenylist  // []) + ($f.terminalDenylist  // [])) | unique) |
                .mcpAllowlist      = (((.mcpAllowlist      // []) + ($f.mcpAllowlist      // [])) | unique) |
                .mcpDenylist       = (((.mcpDenylist       // []) + ($f.mcpDenylist       // [])) | unique)
            )' "$@"
            ;;
        cursor_cli|claude)
            jq -s -S 'reduce .[] as $f ({permissions:{allow:[],deny:[]}};
                .permissions.allow = (((.permissions.allow // []) + ($f.permissions.allow // [])) | unique) |
                .permissions.deny  = (((.permissions.deny  // []) + ($f.permissions.deny  // [])) | unique)
            )' "$@"
            ;;
    esac
}

# Strip the permission keys from a JSON file so what's left is the
# "passthrough" — everything the engineer has at the top level that we
# don't manage (cli version, editor, claude theme, model, ...).
extract_passthrough() {
    local kind="$1" live="$2"
    case "$kind" in
        cursor_ide)
            jq -S 'del(.terminalAllowlist, .terminalDenylist, .mcpAllowlist, .mcpDenylist)' "$live"
            ;;
        cursor_cli|claude)
            jq -S 'del(.permissions)' "$live"
            ;;
    esac
}

# True (exit 0) when a passthrough JSON has no top-level keys.
is_empty_object() {
    local f="$1"
    local n
    n=$(jq 'if type == "object" then (keys | length) else 0 end' "$f" 2>/dev/null || printf '0')
    [ "$n" = "0" ]
}

# ---------------------------------------------------------------------------
# Sidecar discovery
# ---------------------------------------------------------------------------
# All ORG sidecars (including this $ORG's, excluding only the user-managed
# one). The renderer enumerates from disk so uninstall -- which deletes our
# sidecar before re-rendering -- naturally drops our entries.

list_org_sidecars() {
    local stem="$1" dir="$2"
    [ -d "$dir" ] || return 0
    local f base
    while IFS= read -r -d '' f; do
        base=$(basename "$f")
        case "$base" in
            ".$stem.user-managed.json")     continue ;;
            *)                              printf '%s\n' "$f" ;;
        esac
    done < <(find "$dir" -maxdepth 1 -type f -name ".$stem.*-managed.json" -print0 2>/dev/null)
}

# Sidecars from other $ORGs only (used by user-managed promotion when we want
# the "expected without user AND without our org" baseline -- our org's
# sidecar is recomputable from meta and represented by $our_render there).
list_other_org_sidecars() {
    local stem="$1" dir="$2"
    [ -d "$dir" ] || return 0
    local f base
    while IFS= read -r -d '' f; do
        base=$(basename "$f")
        case "$base" in
            ".$stem.${ORG}-managed.json")  continue ;;
            ".$stem.user-managed.json")     continue ;;
            *)                              printf '%s\n' "$f" ;;
        esac
    done < <(find "$dir" -maxdepth 1 -type f -name ".$stem.*-managed.json" -print0 2>/dev/null)
}

# ---------------------------------------------------------------------------
# Render pipeline: sidecars + user + passthrough -> target schema bytes
# ---------------------------------------------------------------------------
# Reads org sidecars from disk. If an EXTRA fifth argument is passed
# (typically our meta-derived render for the dry-run path where we haven't
# written our sidecar yet), it is treated as an additional org-managed
# input.  Caller is responsible for choosing whether to include our org's
# contribution: install/dry-run pass it through; uninstall/status/diff
# rely only on what's on disk.

render_one_target() {
    local stem="$1" dir="$2" kind="$3" out="$4" extra="${5:-}" exclude_ours="${6:-}"

    local args=()
    [ -n "$extra" ] && [ -f "$extra" ] && args+=("$extra")

    local sidecar
    while IFS= read -r sidecar; do
        [ -n "$sidecar" ] || continue
        # Skip our own on-disk sidecar when an extra render supersedes it
        # OR when the caller explicitly wants to render "as if uninstalled".
        if [ -n "$extra" ] || [ "$exclude_ours" = "1" ]; then
            case "$(basename "$sidecar")" in
                ".$stem.${ORG}-managed.json") continue ;;
            esac
        fi
        args+=("$sidecar")
    done < <(list_org_sidecars "$stem" "$dir")

    local user_file
    user_file=$(user_sidecar "$stem" "$dir")
    [ -f "$user_file" ] && args+=("$user_file")

    local merged
    merged=$(mktemp)
    if [ "${#args[@]}" -eq 0 ]; then
        # No sidecars and no user-managed -- render an empty target-schema doc.
        case "$kind" in
            cursor_ide) printf '{}\n'                                      > "$merged" ;;
            *)          printf '{"permissions":{"allow":[],"deny":[]}}\n'  > "$merged" ;;
        esac
    else
        union_target_schema "$kind" "${args[@]}" > "$merged"
    fi

    # Layer the passthrough on top: merged wins for overlapping keys
    # (passthrough is only supposed to carry NON-permission keys, so there
    # should be no conflict; merged-wins is the defensive choice).
    local pt
    pt=$(passthrough_path "$stem" "$dir")
    if [ -f "$pt" ]; then
        jq -s -S '.[0] * .[1]' "$pt" "$merged" > "$out"
    else
        jq -S '.' "$merged" > "$out"
    fi
    rm -f "$merged"
}

# ---------------------------------------------------------------------------
# User-managed sidecar promotion
# ---------------------------------------------------------------------------
# Compares the live file against an "expected without user" render and
# captures any permission entries the engineer added by hand into
# .<stem>.user-managed.json. Also refreshes .<stem>.passthrough.json from
# whatever non-permission top-level keys the live file currently has.

promote_user_edits() {
    local stem="$1" dir="$2" kind="$3"
    local live
    live=$(target_path "$stem" "$dir")
    [ -f "$live" ] || return 0

    # 1) Refresh the passthrough sidecar from live (idempotent).
    local pt new_pt
    pt=$(passthrough_path "$stem" "$dir")
    new_pt=$(mktemp)
    extract_passthrough "$kind" "$live" > "$new_pt"

    local should_write_pt=0
    if is_empty_object "$new_pt"; then
        # Nothing to preserve. Leave a stale passthrough alone (engineer may
        # be mid-edit) but don't create an empty one.
        :
    elif [ ! -f "$pt" ] || ! cmp -s "$new_pt" "$pt"; then
        should_write_pt=1
    fi
    if [ "$should_write_pt" = "1" ] && [ "$DRY_RUN" != "1" ]; then
        atomic_write "$pt" "$new_pt"
    fi
    rm -f "$new_pt"

    # 2) Compute what live WOULD be without user-managed entries.
    local our_render expected_no_user
    our_render=$(mktemp)
    expected_no_user=$(mktemp)
    render_target_schema "$kind" "$ALLOWLISTS_SRC" > "$our_render"

    local args=("$our_render")
    local other
    while IFS= read -r other; do
        [ -n "$other" ] && args+=("$other")
    done < <(list_other_org_sidecars "$stem" "$dir")

    union_target_schema "$kind" "${args[@]}" > "$expected_no_user"
    rm -f "$our_render"

    # 3) Diff live against expected; merge new entries into user sidecar.
    local user_file user_in user_out
    user_file=$(user_sidecar "$stem" "$dir")
    user_in=$(mktemp)
    user_out=$(mktemp)
    if [ -f "$user_file" ]; then
        cp "$user_file" "$user_in"
    else
        case "$kind" in
            cursor_ide) printf '{}\n'                                       > "$user_in" ;;
            *)          printf '{"permissions":{"allow":[],"deny":[]}}\n'   > "$user_in" ;;
        esac
    fi

    case "$kind" in
        cursor_ide)
            jq -s -S '
                .[0] as $live | .[1] as $exp | .[2] as $u |
                {
                    terminalAllowlist: ((($u.terminalAllowlist // []) + (($live.terminalAllowlist // []) - ($exp.terminalAllowlist // []))) | unique),
                    terminalDenylist:  ((($u.terminalDenylist  // []) + (($live.terminalDenylist  // []) - ($exp.terminalDenylist  // []))) | unique),
                    mcpAllowlist:      ((($u.mcpAllowlist      // []) + (($live.mcpAllowlist      // []) - ($exp.mcpAllowlist      // []))) | unique),
                    mcpDenylist:       ((($u.mcpDenylist       // []) + (($live.mcpDenylist       // []) - ($exp.mcpDenylist       // []))) | unique)
                }
                | with_entries(select(.value | length > 0))
            ' "$live" "$expected_no_user" "$user_in" > "$user_out"
            ;;
        cursor_cli|claude)
            jq -s -S '
                .[0] as $live | .[1] as $exp | .[2] as $u |
                {
                    permissions: {
                        allow: ((($u.permissions.allow // []) + (($live.permissions.allow // []) - ($exp.permissions.allow // []))) | unique),
                        deny:  ((($u.permissions.deny  // []) + (($live.permissions.deny  // []) - ($exp.permissions.deny  // []))) | unique)
                    }
                }
            ' "$live" "$expected_no_user" "$user_in" > "$user_out"
            ;;
    esac
    rm -f "$expected_no_user" "$user_in"

    # 4) Persist user-sidecar iff it has any content (skip empty {}/empty arrays).
    local total
    case "$kind" in
        cursor_ide)
            total=$(jq '[(.terminalAllowlist // []), (.terminalDenylist // []), (.mcpAllowlist // []), (.mcpDenylist // [])] | map(length) | add // 0' "$user_out")
            ;;
        cursor_cli|claude)
            total=$(jq '[(.permissions.allow // []), (.permissions.deny // [])] | map(length) | add // 0' "$user_out")
            ;;
    esac

    if [ "$total" != "0" ]; then
        if [ "$DRY_RUN" != "1" ]; then
            if [ ! -f "$user_file" ] || ! cmp -s "$user_out" "$user_file"; then
                atomic_write "$user_file" "$user_out"
            fi
        fi
    fi
    rm -f "$user_out"
}

# ---------------------------------------------------------------------------
# History rotation (.history/<stem>.json.N, unbounded, per-file counters)
# ---------------------------------------------------------------------------

rotate_history() {
    local stem="$1" dir="$2"
    local live
    live=$(target_path "$stem" "$dir")
    [ -f "$live" ] || return 0       # nothing to back up (first install)

    local hist
    hist=$(history_dir_of "$dir")
    mkdir -p "$hist"

    # Find max existing .N for this stem, then shift each down (N -> N+1).
    local max=0 entry n
    while IFS= read -r entry; do
        n="${entry##*.}"
        case "$n" in
            ''|*[!0-9]*) continue ;;
        esac
        [ "$n" -gt "$max" ] && max="$n"
    done < <(find "$hist" -maxdepth 1 -name "$stem.json.[0-9]*" -type f 2>/dev/null)

    local i src dst
    i="$max"
    while [ "$i" -ge 1 ]; do
        src="$hist/$stem.json.$i"
        dst="$hist/$stem.json.$((i+1))"
        [ -f "$src" ] && mv -- "$src" "$dst"
        i=$((i - 1))
    done

    cp -- "$live" "$hist/$stem.json.1"
}

# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

atomic_write() {
    local target="$1" source="$2"
    local tmp="${target}.tmp.$$"
    mkdir -p "$(dirname "$target")"
    cp -- "$source" "$tmp"
    mv -- "$tmp" "$target"
}

# ---------------------------------------------------------------------------
# First-install conflict guardrail
# ---------------------------------------------------------------------------
# If .history/<stem>.json.1 already exists but we never wrote a sidecar for
# this $ORG, somebody else has been managing this file (or the engineer
# pre-seeded .history/ by hand). Warn and abort rather than silently
# overwriting the live file.

guardrail_first_install() {
    local stem="$1" dir="$2"
    local hist1 sidecar
    hist1=$(history_file "$stem" "$dir" 1)
    sidecar=$(org_sidecar "$stem" "$dir")
    if [ -f "$hist1" ] && [ ! -f "$sidecar" ]; then
        printf 'error: %s exists but %s does not.\n' \
            "$(pretty_path "$hist1")" "$(pretty_path "$sidecar")" >&2
        printf '       refusing to overwrite a live file we did not install previously.\n' >&2
        printf '       to proceed: remove %s and re-run, or restore the previous\n' \
            "$(pretty_path "$hist1")" >&2
        printf '       file with `make restore-allowlists N=1`.\n' >&2
        ABORTED=1
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Foreign-file detection inside .history/ (read-only; informational only)
# ---------------------------------------------------------------------------

note_foreign_history_files() {
    local dir="$1"
    local hist
    hist=$(history_dir_of "$dir")
    [ -d "$hist" ] || return 0

    local stems=()
    local s
    while IFS= read -r s; do
        [ -n "$s" ] && stems+=("$s")
    done < <(stems_in_dir "$dir")

    local entry name matched ok_pat
    while IFS= read -r -d '' entry; do
        name=$(basename "$entry")
        matched=0
        for s in "${stems[@]}"; do
            ok_pat="$s.json.[0-9]*"
            case "$name" in
                $ok_pat) matched=1; break ;;
            esac
        done
        if [ "$matched" = "0" ]; then
            NOTES+=("foreign file in $(pretty_path "$hist"): $name")
        fi
    done < <(find "$hist" -maxdepth 1 -type f -print0 2>/dev/null)
}

# ---------------------------------------------------------------------------
# Per-target install/uninstall/dry-run
# ---------------------------------------------------------------------------

apply_one_target() {
    local stem="$1" dir="$2" kind="$3"
    local live pretty label
    live=$(target_path "$stem" "$dir")
    pretty=$(pretty_path "$live")
    label=$(side_label "$dir")

    guardrail_first_install "$stem" "$dir" || return 1

    # Promote user manual edits before re-rendering.
    promote_user_edits "$stem" "$dir" "$kind"

    # Compute our canonical render from the meta-source.
    local our_render sidecar
    our_render=$(mktemp)
    render_target_schema "$kind" "$ALLOWLISTS_SRC" > "$our_render"

    # Refresh our org sidecar on disk so peer installers see our contribution.
    sidecar=$(org_sidecar "$stem" "$dir")
    if [ ! -f "$sidecar" ] || ! cmp -s "$our_render" "$sidecar"; then
        if [ "$DRY_RUN" != "1" ]; then
            atomic_write "$sidecar" "$our_render"
        fi
    fi

    # Render the full union for the live file (pass our_render as extra so
    # dry-run sees our contribution even when the sidecar isn't on disk yet).
    local proposed
    proposed=$(mktemp)
    render_one_target "$stem" "$dir" "$kind" "$proposed" "$our_render"
    rm -f "$our_render"

    if [ -f "$live" ] && cmp -s "$proposed" "$live"; then
        printf '%-50s = no change (idempotent)%s\n' "$pretty" "$label"
        rm -f "$proposed"
        return 0
    fi

    if [ "$DRY_RUN" = "1" ]; then
        if [ -f "$live" ]; then
            printf '%-50s ~ would re-render (%d bytes)%s\n' "$pretty" "$(wc -c < "$proposed" | tr -d ' ')" "$label"
        else
            printf '%-50s + would create (%d bytes)%s\n'    "$pretty" "$(wc -c < "$proposed" | tr -d ' ')" "$label"
        fi
        rm -f "$proposed"
        return 0
    fi

    if [ -f "$live" ]; then
        rotate_history "$stem" "$dir"
    fi
    atomic_write "$live" "$proposed"
    rm -f "$proposed"

    if [ -f "$live" ]; then
        printf '%-50s + wrote (%d bytes)%s\n' "$pretty" "$(wc -c < "$live" | tr -d ' ')" "$label"
    fi
}

remove_one_target() {
    local stem="$1" dir="$2" kind="$3"
    local live pretty sidecar label
    live=$(target_path "$stem" "$dir")
    pretty=$(pretty_path "$live")
    sidecar=$(org_sidecar "$stem" "$dir")
    label=$(side_label "$dir")

    if [ ! -f "$sidecar" ] && [ ! -f "$live" ]; then
        printf '%-50s = nothing to remove%s\n' "$pretty" "$label"
        return 0
    fi

    # Promote any pending user edits before we drop our sidecar.
    promote_user_edits "$stem" "$dir" "$kind"

    if [ -f "$sidecar" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            printf '%-50s - would remove sidecar %s%s\n' "$pretty" "$(pretty_path "$sidecar")" "$label"
        else
            rm -f -- "$sidecar"
            printf '%-50s - removed sidecar %s%s\n' "$pretty" "$(pretty_path "$sidecar")" "$label"
        fi
    fi

    # Re-render without our sidecar. May produce an empty rendering if no
    # other inputs survive; in that case leave the live file alone (the
    # engineer can delete it manually) -- our contract is "remove ORG's
    # contribution", not "remove the file".
    local proposed
    proposed=$(mktemp)
    render_one_target "$stem" "$dir" "$kind" "$proposed" "" "1"

    if [ -f "$live" ] && cmp -s "$proposed" "$live"; then
        rm -f "$proposed"
        return 0
    fi

    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s ~ would re-render without %s%s\n' "$pretty" "$ORG" "$label"
        rm -f "$proposed"
        return 0
    fi

    [ -f "$live" ] && rotate_history "$stem" "$dir"
    atomic_write "$live" "$proposed"
    rm -f "$proposed"
    printf '%-50s ~ re-rendered without %s%s\n' "$pretty" "$ORG" "$label"
}

# ---------------------------------------------------------------------------
# Status / diff / restore / clean
# ---------------------------------------------------------------------------

status_one_target() {
    local stem="$1" dir="$2" kind="$3"
    local live pretty sidecar label
    live=$(target_path "$stem" "$dir")
    pretty=$(pretty_path "$live")
    sidecar=$(org_sidecar "$stem" "$dir")
    label=$(side_label "$dir")

    if [ ! -f "$live" ]; then
        printf '%-50s -- not installed%s\n' "$pretty" "$label"
        return 0
    fi

    local proposed
    proposed=$(mktemp)
    render_one_target "$stem" "$dir" "$kind" "$proposed"

    local marker entries bytes
    bytes=$(wc -c < "$live" | tr -d ' ')
    case "$kind" in
        cursor_ide)
            entries=$(jq '[(.terminalAllowlist // []), (.terminalDenylist // []), (.mcpAllowlist // []), (.mcpDenylist // [])] | map(length) | add' "$live")
            ;;
        cursor_cli|claude)
            entries=$(jq '[(.permissions.allow // []), (.permissions.deny // [])] | map(length) | add' "$live")
            ;;
    esac
    if cmp -s "$proposed" "$live"; then
        marker="OK current"
    else
        marker="~ drift"
    fi

    local sidecar_note=""
    [ -f "$sidecar" ] && sidecar_note=" (${ORG} sidecar present)"
    printf '%-50s %s (%s bytes, %s entries)%s%s\n' "$pretty" "$marker" "$bytes" "$entries" "$sidecar_note" "$label"
    rm -f "$proposed"
}

diff_one_target() {
    local stem="$1" dir="$2" kind="$3"
    local live pretty label
    live=$(target_path "$stem" "$dir")
    pretty=$(pretty_path "$live")
    label=$(side_label "$dir")

    local proposed
    proposed=$(mktemp)
    render_one_target "$stem" "$dir" "$kind" "$proposed"

    if [ ! -f "$live" ]; then
        printf '%-50s + would create (%s bytes)%s\n' "$pretty" "$(wc -c < "$proposed" | tr -d ' ')" "$label"
        rm -f "$proposed"
        return 0
    fi
    if cmp -s "$proposed" "$live"; then
        printf '%-50s = match%s\n' "$pretty" "$label"
        rm -f "$proposed"
        return 0
    fi

    printf '%s ~ differs:%s\n' "$pretty" "$label"
    diff -u "$live" "$proposed" || true
    rm -f "$proposed"
}

restore_one_target() {
    local stem="$1" dir="$2" kind="$3" n="$4"
    local live pretty src label
    live=$(target_path "$stem" "$dir")
    pretty=$(pretty_path "$live")
    src=$(history_file "$stem" "$dir" "$n")
    label=$(side_label "$dir")

    if [ ! -f "$src" ]; then
        printf '%-50s ! .history/%s.json.%s not found; skipping%s\n' \
            "$pretty" "$stem" "$n" "$label"
        return 0
    fi

    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s ~ would restore from %s%s\n' "$pretty" "$(pretty_path "$src")" "$label"
        return 0
    fi

    # Snapshot the source into a temp file BEFORE rotating — rotate_history
    # shifts .N→.N+1, which overwrites the path at $src with new content
    # (the live file), making the original backup unreachable via $src.
    local snap
    snap=$(mktemp)
    cp -- "$src" "$snap"

    # Rotate the current live BEFORE replacing it so the restore itself is reversible.
    [ -f "$live" ] && rotate_history "$stem" "$dir"
    atomic_write "$live" "$snap"
    rm -f "$snap"
    printf '%-50s + restored from %s%s\n' "$pretty" "$(pretty_path "$src")" "$label"
}

clean_one_dir() {
    local dir="$1"
    local hist
    hist=$(history_dir_of "$dir")
    [ -d "$hist" ] || return 0
    local pretty
    pretty=$(pretty_path "$hist")
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s - would remove .history/\n' "$pretty"
    else
        rm -rf -- "$hist"
        printf '%-50s - removed .history/\n' "$pretty"
    fi
}

# True (exit 0) when some OTHER org's sidecar still manages a target in $dir.
# Used to warn before removing the shared .history/ on uninstall.
dir_has_other_org_sidecars() {
    local dir="$1" stem
    while IFS= read -r stem; do
        [ -n "$stem" ] || continue
        [ -n "$(list_other_org_sidecars "$stem" "$dir")" ] && return 0
    done < <(stems_in_dir "$dir")
    return 1
}

# After a successful uninstall, offer to remove the leftover .history/ dirs.
# Default is KEEP. $REMOVE_HISTORY skips the prompt. When unset, prompt inline
# on the controlling terminal (/dev/tty) -- not stdout/stderr -- so it pauses
# correctly even when invoked from `make` (which can buffer or redirect the
# recipe's streams). With no usable terminal (CI, pipes) the prompt is skipped
# and .history/ is kept.
maybe_remove_history_on_uninstall() {
    local dirs=() seen="" stem dir kind hist
    while IFS='|' read -r stem dir kind; do
        case "$seen" in *"|$dir|"*) continue ;; esac
        seen="$seen|$dir|"
        hist=$(history_dir_of "$dir")
        [ -d "$hist" ] && dirs+=("$dir")
    done < <(all_targets)

    [ "${#dirs[@]}" -gt 0 ] || return 0

    local decision=""
    case "$REMOVE_HISTORY" in
        1|y|Y|yes|YES) decision="remove" ;;
        0|n|N|no|NO)   decision="keep" ;;
        *)
            if [ -r /dev/tty ] && [ -w /dev/tty ]; then
                # Drive both the message and the read off /dev/tty so the
                # prompt renders inline and waits, regardless of how make
                # wired stdout/stderr.
                {
                    printf '\nUninstall complete. Backup history still exists in:\n'
                    for dir in "${dirs[@]}"; do
                        printf '  %s\n' "$(pretty_path "$(history_dir_of "$dir")")"
                    done
                    for dir in "${dirs[@]}"; do
                        if dir_has_other_org_sidecars "$dir"; then
                            printf 'warning: %s also holds backups for other installers; removing it discards those too.\n' \
                                "$(pretty_path "$(history_dir_of "$dir")")"
                        fi
                    done
                } > /dev/tty
                local reply=""
                read -r -p 'Remove backup history (.history/)? [y/N] ' reply < /dev/tty 2> /dev/tty || reply=""
                case "$reply" in
                    y|Y|yes|YES) decision="remove" ;;
                    *)           decision="keep" ;;
                esac
            else
                decision="keep"
            fi
            ;;
    esac

    if [ "$decision" = "remove" ]; then
        for dir in "${dirs[@]}"; do
            clean_one_dir "$dir"
        done
    else
        printf '%-50s = kept .history/ (backups preserved)\n' "(uninstall)"
    fi
}

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

print_header() {
    local verb="$1"
    printf '%s: org=%s, source=%s\n' \
        "$verb" "$ORG" "$(pretty_path "$ALLOWLISTS_SRC")"
    if [ -n "$WIN_HOME" ]; then
        printf '       windows host home detected at %s (dual pass)\n' \
            "$(pretty_path "$WIN_HOME")"
    fi
}

print_notes() {
    [ "${#NOTES[@]}" -gt 0 ] || return 0
    printf '\nnotes:\n'
    local n
    for n in "${NOTES[@]}"; do
        printf '  ! %s\n' "$n"
    done
}

print_conflicts() {
    [ "${#CONFLICTS[@]}" -gt 0 ] || return 0
    printf '\nconflicts (left untouched):\n'
    local c
    for c in "${CONFLICTS[@]}"; do
        printf '  ! %s\n' "$c"
    done
}

# Walk each target and gather foreign-history notes. Computed once per
# directory (since multiple targets share .history/).
collect_foreign_notes() {
    local seen=""
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        case "$seen" in
            *"|$dir|"*) continue ;;
        esac
        seen="$seen|$dir|"
        note_foreign_history_files "$dir"
    done < <(all_targets)
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

cmd_install() {
    DRY_RUN=0
    init_win_home
    init_win_dests
    acquire_lock
    print_header "install-allowlists"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        apply_one_target "$stem" "$dir" "$kind" || true
        [ "$ABORTED" = "1" ] && break
    done < <(all_targets)
    collect_foreign_notes
    print_notes
    print_conflicts
    if [ "$ABORTED" = "1" ]; then exit 1; fi
}

cmd_uninstall() {
    DRY_RUN=0
    init_win_home
    init_win_dests
    acquire_lock
    print_header "uninstall-allowlists"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        remove_one_target "$stem" "$dir" "$kind"
    done < <(all_targets)
    maybe_remove_history_on_uninstall
    print_notes
    print_conflicts
}

cmd_dry_run() {
    DRY_RUN=1
    init_win_home
    init_win_dests
    acquire_lock
    print_header "dry-run-allowlists"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        apply_one_target "$stem" "$dir" "$kind" || true
        [ "$ABORTED" = "1" ] && break
    done < <(all_targets)
    collect_foreign_notes
    print_notes
    print_conflicts
    if [ "$ABORTED" = "1" ]; then exit 1; fi
}

cmd_status() {
    DRY_RUN=1
    init_win_home
    init_win_dests
    print_header "status-allowlists"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        status_one_target "$stem" "$dir" "$kind"
    done < <(all_targets)
    collect_foreign_notes
    print_notes
    print_conflicts
}

cmd_diff() {
    DRY_RUN=1
    init_win_home
    init_win_dests
    print_header "diff-allowlists"
    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        diff_one_target "$stem" "$dir" "$kind"
    done < <(all_targets)
}

cmd_restore() {
    if [ -z "$RESTORE_N" ]; then
        printf 'error: RESTORE_N must be set (e.g. `make restore-allowlists N=2`)\n' >&2
        exit 2
    fi
    case "$RESTORE_N" in
        ''|*[!0-9]*) printf 'error: RESTORE_N must be a positive integer\n' >&2; exit 2 ;;
    esac
    [ "$RESTORE_N" -ge 1 ] || { printf 'error: RESTORE_N must be >= 1\n' >&2; exit 2; }

    DRY_RUN=0
    init_win_home
    init_win_dests
    acquire_lock
    print_header "restore-allowlists"

    local restrict_stem=""
    if [ -n "$RESTORE_FILE" ]; then
        case "$RESTORE_FILE" in
            permissions.json|cli-config.json|settings.json)
                restrict_stem="${RESTORE_FILE%.json}"
                ;;
            *)
                printf 'error: RESTORE_FILE must be one of permissions.json, cli-config.json, settings.json\n' >&2
                exit 2
                ;;
        esac
    fi

    local stem dir kind
    while IFS='|' read -r stem dir kind; do
        if [ -n "$restrict_stem" ] && [ "$stem" != "$restrict_stem" ]; then
            continue
        fi
        restore_one_target "$stem" "$dir" "$kind" "$RESTORE_N"
    done < <(all_targets)
}

cmd_clean() {
    DRY_RUN=0
    init_win_home
    init_win_dests
    acquire_lock
    print_header "clean-allowlists"
    local seen="" stem dir kind
    while IFS='|' read -r stem dir kind; do
        case "$seen" in
            *"|$dir|"*) continue ;;
        esac
        seen="$seen|$dir|"
        clean_one_dir "$dir"
    done < <(all_targets)
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
usage: $0 {install|uninstall|dry-run|status|diff|restore|clean}

This script is invoked by the agents Makefile with the appropriate environment.
Run \`make help\` from the Makefile directory for user-facing entry points.

Required env: ORG, ALLOWLISTS_SRC
Optional env: CURSOR_DATA_HOME, CLAUDE_DATA_HOME, MAKEFILE_LABEL
              WIN_HOME (auto-detected under WSL; set to "" to disable dual pass)
              WIN_CURSOR_DATA_HOME, WIN_CLAUDE_DATA_HOME (derived from WIN_HOME)
              RESTORE_N (for restore), RESTORE_FILE (for restore, optional)
              REMOVE_HISTORY (for uninstall: yes/no to skip the prompt)
EOF
}

case "${1:-}" in
    install)    MODE=install;    cmd_install ;;
    uninstall)  MODE=uninstall;  cmd_uninstall ;;
    dry-run)    MODE=dry-run;    cmd_dry_run ;;
    status)     MODE=status;     cmd_status ;;
    diff)       MODE=diff;       cmd_diff ;;
    restore)    MODE=restore;    cmd_restore ;;
    clean)      MODE=clean;      cmd_clean ;;
    -h|--help|help|"") usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
