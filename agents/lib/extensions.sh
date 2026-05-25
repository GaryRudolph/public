#!/usr/bin/env bash
# Symlink installer for agent extensions (skills + slash commands).
#
# Cursor and Claude Code discover skills/commands by scanning a directory but
# do not honor any @-import syntax inside those files. A symlink from the
# scanned home-directory location to the in-repo source serves the same role
# as @-import: edit-once, read-everywhere.
#
# Ownership model: the symlink's resolved target is its own marker. A symlink
# under the configured home dir whose target falls inside a managed SRC tree
# is "ours"; anything else is foreign and left untouched. No sidecar manifest.
#
# Required env (set by the calling Makefile):
#   ORG                    installer identity ("personal", "agerpoint", ...)
#   SKILLS_SRC             source dir for skills   (folder per skill)
#   COMMANDS_SRC           source dir for commands (one *.md per command)
#
# Optional env (defaults shown):
#   CURSOR_SKILLS_HOME     ~/.cursor/skills
#   CLAUDE_SKILLS_HOME     ~/.claude/skills
#   CLAUDE_COMMANDS_HOME   ~/.claude/commands
#   AGENTS_DIR             dirname(SKILLS_SRC)  (used only for the header line)
#
# Subcommands:
#   install      Two-pass: orphan cleanup (sources deleted from the repo
#                lose their symlinks) + reconcile sources (create/refresh).
#   uninstall    Remove every symlink under each home dir whose target lives
#                under our SRC, regardless of whether the source still exists.
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

MODE="install"            # install | uninstall | dry-run | status
DRY_RUN=0
CONFLICTS=()              # accumulated, printed at the end

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
        # Cwd::abs_path returns empty for nonexistent paths on macOS perl.
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
# Tuple definition
# ---------------------------------------------------------------------------
# Each line: src_dir|dest_dir|kind  where kind is "skill" or "command".

tuples() {
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$CURSOR_SKILLS_HOME"
    printf '%s|%s|skill\n'   "$SKILLS_SRC"   "$CLAUDE_SKILLS_HOME"
    printf '%s|%s|command\n' "$COMMANDS_SRC" "$CLAUDE_COMMANDS_HOME"
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
# State detection
# ---------------------------------------------------------------------------
# For each (src_item, dest) pair, classify dest as:
#   absent      dest does not exist (not even as a symlink)
#   ok          dest is a symlink that resolves exactly to src_item
#   restore     dest is a symlink resolving under our SRC but to a different
#               source path (e.g. SRC was reorganized)
#   broken_ours dest is a broken symlink whose stored target is under our SRC
#   foreign     dest is a symlink pointing outside our SRC
#   nonsymlink  dest is a real file or directory

classify_dest() {
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

        # Broken symlink: classify by the canonicalized stored target.
        if path_under "$link_canon" "$src_real"; then
            printf 'broken_ours'
        else
            printf 'foreign'
        fi
        return
    fi

    printf 'nonsymlink'
}

# ---------------------------------------------------------------------------
# Pass 1: orphan cleanup
# ---------------------------------------------------------------------------
# Walk symlinks directly under dest_dir. For any whose stored target is under
# our SRC AND whose target no longer exists, remove it. Foreign symlinks and
# live ones are untouched.

orphan_cleanup() {
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
        [ -e "$entry" ] && continue   # still live, leave alone

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
purge_ours() {
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

# ---------------------------------------------------------------------------
# Pass 2: source reconcile
# ---------------------------------------------------------------------------

reconcile_sources() {
    local src_dir="$1" dest_dir="$2" kind="$3"
    [ -d "$src_dir" ] || return 0

    local src_item dest pretty state
    while IFS= read -r src_item; do
        [ -n "$src_item" ] || continue
        dest=$(dest_path_for "$src_item" "$dest_dir")
        pretty=$(pretty_path "$dest")
        state=$(classify_dest "$src_item" "$dest" "$src_dir")

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
# Subcommands
# ---------------------------------------------------------------------------

print_header() {
    local verb="$1"
    printf '%s: org=%s, agents=%s\n' "$verb" "$ORG" "$(pretty_path "$AGENTS_DIR")"
}

print_conflicts() {
    [ "${#CONFLICTS[@]}" -gt 0 ] || return 0
    printf '\nconflicts (left untouched):\n'
    local c
    for c in "${CONFLICTS[@]}"; do
        printf '  ! %s\n' "$c"
    done
}

run_install_passes() {
    local src dest kind
    while IFS='|' read -r src dest kind; do
        orphan_cleanup "$src" "$dest" "$kind"
        reconcile_sources "$src" "$dest" "$kind"
    done < <(tuples)
}

cmd_install() {
    DRY_RUN=0
    print_header "install-extensions"
    run_install_passes
    print_conflicts
}

cmd_uninstall() {
    DRY_RUN=0
    print_header "uninstall-extensions"
    local src dest kind
    while IFS='|' read -r src dest kind; do
        purge_ours "$src" "$dest" "$kind"
    done < <(tuples)
    print_conflicts
}

cmd_dry_run() {
    DRY_RUN=1
    print_header "dry-run-extensions"
    run_install_passes
    print_conflicts
}

cmd_status() {
    DRY_RUN=1
    print_header "status-extensions"

    local src dest kind pretty state src_item d
    while IFS='|' read -r src dest kind; do
        if [ ! -d "$src" ]; then
            printf '%-50s (source dir missing: %s)\n' \
                "$(pretty_path "$dest")/" "$(pretty_path "$src")"
            continue
        fi

        # Live + missing sources from the repo's point of view.
        while IFS= read -r src_item; do
            [ -n "$src_item" ] || continue
            d=$(dest_path_for "$src_item" "$dest")
            pretty=$(pretty_path "$d")
            state=$(classify_dest "$src_item" "$d" "$src")
            case "$state" in
                ok)          printf '%-50s = present (%s)\n' "$pretty" "$kind" ;;
                absent)      printf '%-50s + missing (%s)\n' "$pretty" "$kind" ;;
                restore)     printf '%-50s ~ stale (%s, source path changed)\n' "$pretty" "$kind" ;;
                broken_ours) printf '%-50s ~ broken (%s, our symlink target gone)\n' "$pretty" "$kind" ;;
                foreign)     printf '%-50s ! conflict (%s, managed elsewhere)\n' "$pretty" "$kind" ;;
                nonsymlink)  printf '%-50s ! conflict (%s, non-symlink at target)\n' "$pretty" "$kind" ;;
            esac
        done < <(enumerate_sources "$src" "$kind")

        # Orphans: our symlinks in dest with no matching source in the repo.
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
    done < <(tuples)
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
usage: $0 {install|uninstall|dry-run|status}

Installs and maintains symlinks for agent skills and slash commands.
Invoked by the agents Makefile with the appropriate environment.
EOF
}

case "${1:-}" in
    install)    MODE=install;    cmd_install ;;
    uninstall)  MODE=uninstall;  cmd_uninstall ;;
    dry-run)    MODE=dry-run;    cmd_dry_run ;;
    status)     MODE=status;     cmd_status ;;
    -h|--help|help|"") usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
