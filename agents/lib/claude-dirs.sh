#!/usr/bin/env bash
# Reports which Claude Code config dirs this installer manages and which it
# doesn't. The managed ones are CLAUDE_CONFIG_DIRS; the others are any
# ~/.claude or ~/.claude-* directory that exists but isn't listed (a routed
# profile such as ~/.claude-lolay that the list is missing, or a stray copy).
# Read-only.
#
# Optional env: CLAUDE_CONFIG_DIRS (default ~/.claude; colon-separated absolute
#               paths), ORG (when set, an unlisted dir that still holds this
#               installer's CLAUDE.md block or allowlist sidecar says so)
#
# Subcommands: status

set -euo pipefail

: "${CLAUDE_CONFIG_DIRS:=$HOME/.claude}"
: "${ORG:=}"

# One Claude config dir per line, from the colon-separated list. Read as text,
# so a space or glob character in a path is kept literally.
claude_dirs() { printf '%s\n' "$CLAUDE_CONFIG_DIRS" | tr ':' '\n' | sed '/^$/d'; }

pretty_path() {
    case "$1" in
        "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;;
        *)         printf '%s' "$1" ;;
    esac
}

# The physical path when the dir exists (so a symlinked spelling of a listed
# dir still matches), else the path as written.
physical() {
    if [ -d "$1" ]; then (cd -P "$1" && pwd -P); else printf '%s' "${1%/}"; fi
}

is_listed() {
    local dir want
    want=$(physical "$1")
    while IFS= read -r dir; do
        [ "$(physical "$dir")" = "$want" ] && return 0
    done < <(claude_dirs)
    return 1
}

# Says so when an unlisted dir still holds files this installer wrote.
leftovers() {
    [ -n "$ORG" ] || return 0
    if { [ -f "$1/CLAUDE.md" ] && grep -qF "# >>> $ORG >>>" "$1/CLAUDE.md"; } \
       || [ -e "$1/.settings.$ORG-managed.json" ]; then
        printf '; still holds %s files, so list it and run make uninstall to clear them' "$ORG"
    fi
}

cmd_status() {
    local dir found=0
    printf 'claude config dirs (CLAUDE_CONFIG_DIRS):\n'
    while IFS= read -r dir; do
        if [ -d "$dir" ]; then
            printf '%-50s OK managed\n' "$(pretty_path "$dir")"
        else
            printf '%-50s ! listed but not found\n' "$(pretty_path "$dir")"
        fi
    done < <(claude_dirs)
    for dir in "$HOME"/.claude "$HOME"/.claude-*; do
        [ -d "$dir" ] || continue
        is_listed "$dir" && continue
        found=1
        printf '%-50s ? not managed; add it to CLAUDE_CONFIG_DIRS in agents/local.mk%s\n' \
            "$(pretty_path "$dir")" "$(leftovers "$dir")"
    done
    [ "$found" = "1" ] || printf 'no other ~/.claude* dirs found\n'
    printf '\n'
}

case "${1:-}" in
    status) cmd_status ;;
    *) printf 'usage: %s status\n' "$0" >&2; exit 2 ;;
esac
