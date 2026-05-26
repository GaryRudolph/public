#!/usr/bin/env bash
# Installer for agent extensions (skills + slash commands).
#
# Cursor and Claude Code discover skills/commands by scanning a directory but
# do not honor any @-import syntax inside those files. A symlink from the
# scanned home-directory location to the in-repo source serves the same role
# as @-import: edit-once, read-everywhere.
#
# Two passes on every subcommand:
#
#   1. Unix-side pass (always runs against $HOME). Mode = symlink. Ownership
#      marker = the symlink's canonical target falls under our SKILLS_SRC or
#      COMMANDS_SRC. Foreign symlinks and non-symlinks are left untouched.
#
#   2. Windows-host pass (runs against $WIN_HOME when set, or auto-detected
#      under WSL the same way blocks.sh does it). Mode = COPY, because
#      Windows-native Cursor / Claude Code can't read WSL paths. Ownership
#      marker = a hidden .${ORG}-managed file dropped inside each managed
#      skill directory, and a sidecar .${ORG}-managed file next to each
#      managed command file. Foreign content (anything without our marker)
#      is left untouched.
#
# The Windows copy goes stale until the next `make install` from WSL — same
# trade-off blocks.sh already documents for its inlined Windows-side files.
#
# Required env (set by the calling Makefile):
#   ORG                      installer identity (e.g. "personal")
#   SKILLS_SRC               source dir for skills   (folder per skill)
#   COMMANDS_SRC             source dir for commands (one *.md per command)
#
# Optional env (defaults shown):
#   CURSOR_SKILLS_HOME       ~/.cursor/skills
#   CLAUDE_SKILLS_HOME       ~/.claude/skills
#   CLAUDE_COMMANDS_HOME     ~/.claude/commands
#   WIN_HOME                 (empty; auto-detected when /proc/version contains "microsoft")
#   WIN_CURSOR_SKILLS_HOME   $WIN_HOME/.cursor/skills
#   WIN_CLAUDE_SKILLS_HOME   $WIN_HOME/.claude/skills
#   WIN_CLAUDE_COMMANDS_HOME $WIN_HOME/.claude/commands
#   AGENTS_DIR               dirname(SKILLS_SRC)  (used only for the header line)
#
# Subcommands:
#   install      Reconcile both passes (unix symlinks + windows copies).
#   uninstall    Remove every managed entry from both passes.
#   dry-run      Same as install but no disk writes.
#   status       Per-extension report; no writes.

set -euo pipefail

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

: "${ORG:?ORG must be set}"
: "${SKILLS_SRC:?SKILLS_SRC must be set}"
: "${COMMANDS_SRC:?COMMANDS_SRC must be set}"
: "${CURSOR_SKILLS_HOME:=$HOME/.cursor/skills}"
: "${CLAUDE_SKILLS_HOME:=$HOME/.claude/skills}"
: "${CLAUDE_COMMANDS_HOME:=$HOME/.claude/commands}"
: "${AGENTS_DIR:=$(dirname "$SKILLS_SRC")}"
: "${WIN_HOME:=}"

MARKER=".${ORG}-managed"

DRY_RUN=0
CONFLICTS=()

# ---------------------------------------------------------------------------
# Detection: WSL + Windows-host home (mirrors blocks.sh)
# ---------------------------------------------------------------------------

is_wsl() {
    [ -r /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null
}

detect_win_home() {
    is_wsl || return 1
    command -v cmd.exe >/dev/null 2>&1 || return 1
    command -v wslpath >/dev/null 2>&1 || return 1

    local userprofile wsl_path
    userprofile=$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' || true)
    [ -n "$userprofile" ] || return 1

    wsl_path=$(wslpath "$userprofile" 2>/dev/null || true)
    [ -n "$wsl_path" ] && [ -d "$wsl_path" ] || return 1

    printf '%s' "$wsl_path"
}

init_win_home() {
    if [ -n "$WIN_HOME" ]; then
        return
    fi
    if is_wsl; then
        local detected
        if detected=$(detect_win_home 2>/dev/null); then
            WIN_HOME="$detected"
        else
            printf 'note: WSL detected but Windows host home could not be resolved\n' >&2
            printf '      (cmd.exe interop or wslpath unavailable; Windows-native\n' >&2
            printf '      tools will not see the extensions until this is fixed)\n' >&2
        fi
    fi
}

# Initialize the per-harness Windows dest paths now that WIN_HOME may have
# been auto-detected. Safe to call repeatedly; only sets vars that are empty.
init_win_dests() {
    [ -n "$WIN_HOME" ] || return 0
    : "${WIN_CURSOR_SKILLS_HOME:=$WIN_HOME/.cursor/skills}"
    : "${WIN_CLAUDE_SKILLS_HOME:=$WIN_HOME/.claude/skills}"
    : "${WIN_CLAUDE_COMMANDS_HOME:=$WIN_HOME/.claude/commands}"
}

# ---------------------------------------------------------------------------
# Portable path utilities
# ---------------------------------------------------------------------------

# Resolve a path to its canonical absolute form. Portable across macOS (BSD
# readlink has no -f) and Linux. Empty stdout if the path can't be resolved.
resolve_path() {
    local p="$1"
    if command -v greadlink >/dev/null 2>&1; then
        greadlink -f -- "$p" 2>/dev/null || true
    elif readlink -f -- "$p" >/dev/null 2>&1; then
        readlink -f -- "$p"
    elif command -v perl >/dev/null 2>&1; then
        perl -MCwd -le 'print Cwd::abs_path(shift)' "$p" 2>/dev/null || true
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$p" 2>/dev/null || true
    fi
}

# Read a symlink's stored target and return it as an absolute, canonical path.
# Works for broken symlinks too: the leaf may not exist, but the parent dir
# is canonicalized so /tmp vs /private/tmp (macOS) doesn't break comparisons
# against a canonicalized SRC.
symlink_target_canonical() {
    local link="$1"
    local target dir parent canon
    target=$(readlink -- "$link" 2>/dev/null) || return 1
    case "$target" in
        /*) ;;
        *)  dir=$(dirname -- "$link"); target="$dir/$target" ;;
    esac
    parent=$(dirname -- "$target")
    canon=$(resolve_path "$parent")
    if [ -n "$canon" ]; then
        printf '%s/%s' "$canon" "$(basename -- "$target")"
    else
        printf '%s' "$target"
    fi
}

# True if $1 (path) lives under $2 (path). Pure string comparison; both args
# should already be canonical or both should already be the same shape.
path_under() {
    local child="$1" parent="$2"
    [ -n "$parent" ] || return 1
    case "$child" in
        "$parent"|"$parent"/*) return 0 ;;
        *)                     return 1 ;;
    esac
}

# Shorten an absolute path for display: $HOME -> ~, otherwise as-is.
pretty_path() {
    local p="$1"
    case "$p" in
        "$HOME"/*) printf '~/%s' "${p#"$HOME"/}" ;;
        *)         printf '%s' "$p" ;;
    esac
}

# ---------------------------------------------------------------------------
# Source enumeration (shared by both passes)
# ---------------------------------------------------------------------------

# Each tuple line: src_dir|dest_dir|kind  where kind is "skill" or "command".

unix_tuples() {
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$CURSOR_SKILLS_HOME"
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$CLAUDE_SKILLS_HOME"
    printf '%s|%s|command\n' "$COMMANDS_SRC" "$CLAUDE_COMMANDS_HOME"
}

win_tuples() {
    [ -n "$WIN_HOME" ] || return 0
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$WIN_CURSOR_SKILLS_HOME"
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$WIN_CLAUDE_SKILLS_HOME"
    printf '%s|%s|command\n' "$COMMANDS_SRC" "$WIN_CLAUDE_COMMANDS_HOME"
}

# Enumerate source items under $src_dir according to $kind. Prints absolute
# paths, one per line. README.md and other non-matching entries are excluded.
enumerate_sources() {
    local src="$1" kind="$2"
    [ -d "$src" ] || return 0
    case "$kind" in
        skill)
            find "$src" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort
            ;;
        command)
            find "$src" -mindepth 1 -maxdepth 1 -type f -name '*.md' \
                ! -name 'README.md' 2>/dev/null | sort
            ;;
    esac
}

dest_path_for() {
    local src_item="$1" dest_dir="$2"
    printf '%s/%s' "$dest_dir" "$(basename -- "$src_item")"
}

# ---------------------------------------------------------------------------
# UNIX PASS (symlinks)
# ---------------------------------------------------------------------------
# State classification for one (src_item, dest) pair:
#   absent      dest does not exist (not even as a symlink)
#   ok          dest is a symlink that resolves exactly to src_item
#   restore     dest is a symlink resolving under our SRC but to a different
#               source path (e.g. SRC was reorganized)
#   broken_ours dest is a broken symlink whose stored target is under our SRC
#   foreign     dest is a symlink pointing outside our SRC
#   nonsymlink  dest is a real file or directory

classify_unix_dest() {
    local src_item="$1" dest="$2" src_dir="$3"

    local src_real src_item_real
    src_real=$(resolve_path "$src_dir")
    [ -n "$src_real" ] || src_real="$src_dir"
    src_item_real=$(resolve_path "$src_item")
    [ -n "$src_item_real" ] || src_item_real="$src_item"

    if [ ! -L "$dest" ] && [ ! -e "$dest" ]; then
        printf 'absent'
        return
    fi

    if [ -L "$dest" ]; then
        local link_canon link_real
        link_canon=$(symlink_target_canonical "$dest" || printf '')
        link_real=$(resolve_path "$link_canon")

        if [ -n "$link_real" ] && [ -e "$dest" ]; then
            if [ "$link_real" = "$src_item_real" ]; then
                printf 'ok'; return
            fi
            if path_under "$link_real" "$src_real"; then
                printf 'restore'; return
            fi
            printf 'foreign'; return
        fi

        if path_under "$link_canon" "$src_real"; then
            printf 'broken_ours'
        else
            printf 'foreign'
        fi
        return
    fi

    printf 'nonsymlink'
}

# Walk symlinks directly under dest_dir. For any whose stored target is under
# our SRC AND whose target no longer exists, remove it.
unix_orphan_cleanup() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$dest_dir" ] || return 0

    local src_real
    src_real=$(resolve_path "$src_dir")
    [ -n "$src_real" ] || src_real="$src_dir"

    local entry link_canon pretty
    while IFS= read -r -d '' entry; do
        [ -L "$entry" ] || continue
        link_canon=$(symlink_target_canonical "$entry" || printf '')
        path_under "$link_canon" "$src_real" || continue
        [ -e "$entry" ] && continue

        pretty=$(pretty_path "$entry")
        if [ "$DRY_RUN" = "1" ]; then
            printf '%-50s - would remove orphan %s (source deleted)\n' "$pretty" "$kind"
        else
            rm -- "$entry"
            printf '%-50s - removed orphan %s (source deleted)\n' "$pretty" "$kind"
        fi
    done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -print0 2>/dev/null)
}

# Unconditional removal of every symlink under dest_dir whose stored target is
# under our SRC. Used by uninstall.
unix_purge_ours() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$dest_dir" ] || return 0

    local src_real
    src_real=$(resolve_path "$src_dir")
    [ -n "$src_real" ] || src_real="$src_dir"

    local entry link_canon pretty
    while IFS= read -r -d '' entry; do
        [ -L "$entry" ] || continue
        link_canon=$(symlink_target_canonical "$entry" || printf '')
        path_under "$link_canon" "$src_real" || continue

        pretty=$(pretty_path "$entry")
        if [ "$DRY_RUN" = "1" ]; then
            printf '%-50s - would remove %s symlink\n' "$pretty" "$kind"
        else
            rm -- "$entry"
            printf '%-50s - removed %s symlink\n' "$pretty" "$kind"
        fi
    done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -print0 2>/dev/null)
}

unix_reconcile_sources() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$src_dir" ] || return 0

    local src_item dest pretty state
    while IFS= read -r src_item; do
        [ -n "$src_item" ] || continue
        dest=$(dest_path_for "$src_item" "$dest_dir")
        pretty=$(pretty_path "$dest")
        state=$(classify_unix_dest "$src_item" "$dest" "$src_dir")

        case "$state" in
            ok)
                printf '%-50s = no change (%s)\n' "$pretty" "$kind"
                ;;
            absent)
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s + would create %s -> %s\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                else
                    mkdir -p "$dest_dir"
                    ln -snf -- "$src_item" "$dest"
                    printf '%-50s + created %s -> %s\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                fi
                ;;
            restore|broken_ours)
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s ~ would re-point %s -> %s\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                else
                    ln -snf -- "$src_item" "$dest"
                    printf '%-50s ~ re-pointed %s -> %s\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                fi
                ;;
            foreign)
                printf '%-50s ! conflict (%s, symlink managed elsewhere; leaving intact)\n' \
                    "$pretty" "$kind"
                CONFLICTS+=("foreign $kind at $pretty")
                ;;
            nonsymlink)
                printf '%-50s ! conflict (%s, non-symlink exists; leaving intact)\n' \
                    "$pretty" "$kind"
                CONFLICTS+=("non-symlink at $pretty")
                ;;
        esac
    done < <(enumerate_sources "$src_dir" "$kind")
}

# ---------------------------------------------------------------------------
# WINDOWS PASS (copies + marker files)
# ---------------------------------------------------------------------------
# Ownership marker for skills:    <dest_dir>/.${ORG}-managed
# Ownership marker for commands:  <dest_file>.${ORG}-managed (sidecar)
#
# Content-equality check uses `diff -rq --exclude=...`. The --exclude flag is
# supported by both BSD (macOS) and GNU diff. If the check fails for any
# reason, we re-copy — correctness over noise.

# State classification for one (src_item, dest) pair on the Windows pass:
#   absent      dest does not exist
#   ok          dest exists, marker present, contents byte-match source
#   stale       dest exists, marker present, contents differ from source
#   foreign     dest exists, marker absent (we did not install this)

classify_win_dest() {
    local src_item="$1" dest="$2" kind="$3"

    case "$kind" in
        skill)
            if [ ! -e "$dest" ]; then
                printf 'absent'; return
            fi
            if [ ! -d "$dest" ]; then
                printf 'foreign'; return
            fi
            if [ ! -f "$dest/$MARKER" ]; then
                printf 'foreign'; return
            fi
            if diff -rq --exclude="$MARKER" -- "$src_item" "$dest" >/dev/null 2>&1; then
                printf 'ok'; return
            fi
            printf 'stale'
            ;;
        command)
            if [ ! -e "$dest" ]; then
                printf 'absent'; return
            fi
            if [ ! -f "$dest" ]; then
                printf 'foreign'; return
            fi
            if [ ! -f "$(_win_cmd_sidecar "$dest")" ]; then
                printf 'foreign'; return
            fi
            if cmp -s -- "$src_item" "$dest"; then
                printf 'ok'; return
            fi
            printf 'stale'
            ;;
    esac
}

# Sidecar marker path for a command file. We use <dest>.<ORG>-managed so the
# sidecar sorts next to the file it owns (e.g. `mycmd.md` -> `mycmd.md.${ORG}-managed`).
_win_cmd_sidecar() {
    printf '%s.%s' "$1" "${MARKER#.}"
}

win_install_skill() {
    local src_item="$1" dest="$2"
    rm -rf -- "$dest"
    mkdir -p -- "$(dirname "$dest")"
    cp -R -- "$src_item" "$dest"
    : > "$dest/$MARKER"
}

win_install_command() {
    local src_item="$1" dest="$2"
    mkdir -p -- "$(dirname "$dest")"
    cp -- "$src_item" "$dest"
    : > "$(_win_cmd_sidecar "$dest")"
}

win_remove_managed_skill() {
    local dest="$1"
    [ -d "$dest" ] || return 0
    [ -f "$dest/$MARKER" ] || return 0
    rm -rf -- "$dest"
}

win_remove_managed_command() {
    local dest="$1"
    local sidecar
    sidecar=$(_win_cmd_sidecar "$dest")
    [ -f "$sidecar" ] || return 0
    rm -f -- "$dest" "$sidecar"
}

# Walk dest_dir; remove any managed entry whose source no longer exists in the
# repo. Foreign content (no marker) is left untouched.
win_orphan_cleanup() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$dest_dir" ] || return 0

    local entry pretty src_item
    case "$kind" in
        skill)
            while IFS= read -r -d '' entry; do
                [ -d "$entry" ] || continue
                [ -f "$entry/$MARKER" ] || continue
                src_item="$src_dir/$(basename -- "$entry")"
                [ -d "$src_item" ] && continue

                pretty=$(pretty_path "$entry")
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s - would remove orphan %s (source deleted) [win]\n' "$pretty" "$kind"
                else
                    win_remove_managed_skill "$entry"
                    printf '%-50s - removed orphan %s (source deleted) [win]\n' "$pretty" "$kind"
                fi
            done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
            ;;
        command)
            while IFS= read -r -d '' entry; do
                [ -f "$entry" ] || continue
                # Iterate sidecars; the paired file is "$entry without sidecar suffix".
                case "$(basename -- "$entry")" in
                    *.${MARKER#.}) ;;
                    *) continue ;;
                esac
                local paired
                paired="${entry%.${MARKER#.}}"
                src_item="$src_dir/$(basename -- "$paired")"
                [ -f "$src_item" ] && continue

                pretty=$(pretty_path "$paired")
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s - would remove orphan %s (source deleted) [win]\n' "$pretty" "$kind"
                else
                    win_remove_managed_command "$paired"
                    printf '%-50s - removed orphan %s (source deleted) [win]\n' "$pretty" "$kind"
                fi
            done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -type f -print0 2>/dev/null)
            ;;
    esac
}

# Unconditional removal of every managed entry (skill dir with marker, command
# file with sidecar). Used by uninstall.
win_purge_ours() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$dest_dir" ] || return 0

    local entry pretty
    case "$kind" in
        skill)
            while IFS= read -r -d '' entry; do
                [ -d "$entry" ] || continue
                [ -f "$entry/$MARKER" ] || continue
                pretty=$(pretty_path "$entry")
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s - would remove %s copy [win]\n' "$pretty" "$kind"
                else
                    win_remove_managed_skill "$entry"
                    printf '%-50s - removed %s copy [win]\n' "$pretty" "$kind"
                fi
            done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
            ;;
        command)
            while IFS= read -r -d '' entry; do
                [ -f "$entry" ] || continue
                case "$(basename -- "$entry")" in
                    *.${MARKER#.}) ;;
                    *) continue ;;
                esac
                local paired
                paired="${entry%.${MARKER#.}}"
                pretty=$(pretty_path "$paired")
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s - would remove %s copy [win]\n' "$pretty" "$kind"
                else
                    win_remove_managed_command "$paired"
                    printf '%-50s - removed %s copy [win]\n' "$pretty" "$kind"
                fi
            done < <(find "$dest_dir" -mindepth 1 -maxdepth 1 -type f -print0 2>/dev/null)
            ;;
    esac
}

win_reconcile_sources() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$src_dir" ] || return 0

    local src_item dest pretty state
    while IFS= read -r src_item; do
        [ -n "$src_item" ] || continue
        dest=$(dest_path_for "$src_item" "$dest_dir")
        pretty=$(pretty_path "$dest")
        state=$(classify_win_dest "$src_item" "$dest" "$kind")

        case "$state" in
            ok)
                printf '%-50s = no change (%s) [win]\n' "$pretty" "$kind"
                ;;
            absent)
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s + would copy %s from %s [win]\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                else
                    case "$kind" in
                        skill)   win_install_skill   "$src_item" "$dest" ;;
                        command) win_install_command "$src_item" "$dest" ;;
                    esac
                    printf '%-50s + copied %s from %s [win]\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                fi
                ;;
            stale)
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s ~ would refresh %s from %s [win]\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                else
                    case "$kind" in
                        skill)   win_install_skill   "$src_item" "$dest" ;;
                        command) win_install_command "$src_item" "$dest" ;;
                    esac
                    printf '%-50s ~ refreshed %s from %s [win]\n' \
                        "$pretty" "$kind" "$(pretty_path "$src_item")"
                fi
                ;;
            foreign)
                printf '%-50s ! conflict (%s, no %s marker; leaving intact) [win]\n' \
                    "$pretty" "$kind" "$MARKER"
                CONFLICTS+=("foreign $kind at $pretty (win)")
                ;;
        esac
    done < <(enumerate_sources "$src_dir" "$kind")
}

# ---------------------------------------------------------------------------
# Pass orchestration
# ---------------------------------------------------------------------------

run_unix_install_passes() {
    local src dest kind
    while IFS='|' read -r src dest kind; do
        unix_orphan_cleanup "$src" "$dest" "$kind"
        unix_reconcile_sources "$src" "$dest" "$kind"
    done < <(unix_tuples)
}

run_unix_uninstall_passes() {
    local src dest kind
    while IFS='|' read -r src dest kind; do
        unix_purge_ours "$src" "$dest" "$kind"
    done < <(unix_tuples)
}

run_win_install_passes() {
    [ -n "$WIN_HOME" ] || return 0
    local src dest kind
    while IFS='|' read -r src dest kind; do
        win_orphan_cleanup "$src" "$dest" "$kind"
        win_reconcile_sources "$src" "$dest" "$kind"
    done < <(win_tuples)
}

run_win_uninstall_passes() {
    [ -n "$WIN_HOME" ] || return 0
    local src dest kind
    while IFS='|' read -r src dest kind; do
        win_purge_ours "$src" "$dest" "$kind"
    done < <(win_tuples)
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

print_header() {
    local verb="$1"
    printf '%s: org=%s, agents=%s\n' "$verb" "$ORG" "$(pretty_path "$AGENTS_DIR")"
    if [ -n "$WIN_HOME" ]; then
        printf '       windows host home detected at %s (dual pass)\n' "$(pretty_path "$WIN_HOME")"
    fi
}

print_conflicts() {
    [ "${#CONFLICTS[@]}" -gt 0 ] || return 0
    printf '\nconflicts (left untouched):\n'
    local c
    for c in "${CONFLICTS[@]}"; do
        printf '  ! %s\n' "$c"
    done
}

cmd_install() {
    DRY_RUN=0
    init_win_home
    init_win_dests
    print_header "install-extensions"
    run_unix_install_passes
    run_win_install_passes
    print_conflicts
}

cmd_uninstall() {
    DRY_RUN=0
    init_win_home
    init_win_dests
    print_header "uninstall-extensions"
    run_unix_uninstall_passes
    run_win_uninstall_passes
    print_conflicts
}

cmd_dry_run() {
    DRY_RUN=1
    init_win_home
    init_win_dests
    print_header "dry-run-extensions"
    run_unix_install_passes
    run_win_install_passes
    print_conflicts
}

cmd_status() {
    DRY_RUN=1
    init_win_home
    init_win_dests
    print_header "status-extensions"

    # Unix pass status
    local src dest kind pretty state src_item d
    while IFS='|' read -r src dest kind; do
        if [ ! -d "$src" ]; then
            printf '%-50s (source dir missing: %s)\n' \
                "$(pretty_path "$dest")/" "$(pretty_path "$src")"
            continue
        fi

        while IFS= read -r src_item; do
            [ -n "$src_item" ] || continue
            d=$(dest_path_for "$src_item" "$dest")
            pretty=$(pretty_path "$d")
            state=$(classify_unix_dest "$src_item" "$d" "$src")
            case "$state" in
                ok)          printf '%-50s = present (%s)\n' "$pretty" "$kind" ;;
                absent)      printf '%-50s + missing (%s)\n' "$pretty" "$kind" ;;
                restore)     printf '%-50s ~ stale (%s, source path changed)\n' "$pretty" "$kind" ;;
                broken_ours) printf '%-50s ~ broken (%s, our symlink target gone)\n' "$pretty" "$kind" ;;
                foreign)     printf '%-50s ! conflict (%s, managed elsewhere)\n' "$pretty" "$kind" ;;
                nonsymlink)  printf '%-50s ! conflict (%s, non-symlink at target)\n' "$pretty" "$kind" ;;
            esac
        done < <(enumerate_sources "$src" "$kind")

        if [ -d "$dest" ]; then
            local entry link_canon src_real
            src_real=$(resolve_path "$src")
            [ -n "$src_real" ] || src_real="$src"
            while IFS= read -r -d '' entry; do
                [ -L "$entry" ] || continue
                link_canon=$(symlink_target_canonical "$entry" || printf '')
                path_under "$link_canon" "$src_real" || continue
                [ -e "$entry" ] && continue
                printf '%-50s - orphan (%s, source deleted in repo)\n' \
                    "$(pretty_path "$entry")" "$kind"
            done < <(find "$dest" -mindepth 1 -maxdepth 1 -print0 2>/dev/null)
        fi
    done < <(unix_tuples)

    # Windows pass status
    if [ -n "$WIN_HOME" ]; then
        printf '\nwindows host (%s):\n' "$(pretty_path "$WIN_HOME")"
        while IFS='|' read -r src dest kind; do
            if [ ! -d "$src" ]; then
                printf '%-50s (source dir missing: %s)\n' \
                    "$(pretty_path "$dest")/" "$(pretty_path "$src")"
                continue
            fi

            while IFS= read -r src_item; do
                [ -n "$src_item" ] || continue
                d=$(dest_path_for "$src_item" "$dest")
                pretty=$(pretty_path "$d")
                state=$(classify_win_dest "$src_item" "$d" "$kind")
                case "$state" in
                    ok)      printf '%-50s = present (%s) [win]\n' "$pretty" "$kind" ;;
                    absent)  printf '%-50s + missing (%s) [win]\n' "$pretty" "$kind" ;;
                    stale)   printf '%-50s ~ stale (%s, content drift) [win]\n' "$pretty" "$kind" ;;
                    foreign) printf '%-50s ! conflict (%s, no %s marker) [win]\n' \
                                "$pretty" "$kind" "$MARKER" ;;
                esac
            done < <(enumerate_sources "$src" "$kind")

            # Orphans on the windows side
            case "$kind" in
                skill)
                    [ -d "$dest" ] || continue
                    while IFS= read -r -d '' entry; do
                        [ -d "$entry" ] || continue
                        [ -f "$entry/$MARKER" ] || continue
                        src_item="$src/$(basename -- "$entry")"
                        [ -d "$src_item" ] && continue
                        printf '%-50s - orphan (%s, source deleted in repo) [win]\n' \
                            "$(pretty_path "$entry")" "$kind"
                    done < <(find "$dest" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
                    ;;
                command)
                    [ -d "$dest" ] || continue
                    while IFS= read -r -d '' entry; do
                        [ -f "$entry" ] || continue
                        case "$(basename -- "$entry")" in
                            *.${MARKER#.}) ;;
                            *) continue ;;
                        esac
                        local paired
                        paired="${entry%.${MARKER#.}}"
                        src_item="$src/$(basename -- "$paired")"
                        [ -f "$src_item" ] && continue
                        printf '%-50s - orphan (%s, source deleted in repo) [win]\n' \
                            "$(pretty_path "$paired")" "$kind"
                    done < <(find "$dest" -mindepth 1 -maxdepth 1 -type f -print0 2>/dev/null)
                    ;;
            esac
        done < <(win_tuples)
    fi
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
usage: $0 {install|uninstall|dry-run|status}

Installs and maintains agent skills and slash commands across two passes:
unix-side symlinks under \$HOME, and (under WSL) copies under \$WIN_HOME for
Windows-native tools. Invoked by the agents Makefile.
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
