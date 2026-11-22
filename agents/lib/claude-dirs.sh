#!/usr/bin/env bash
# Reports which Claude Code config dirs this installer manages and which it
# doesn't. The managed ones are CLAUDE_CONFIG_DIRS; the others are any
# ~/.claude or ~/.claude-* directory that exists but isn't listed (a routed
# profile such as ~/.claude-lolay that the list is missing, or a stray copy).
# Read-only.
#
# Optional env: CLAUDE_CONFIG_DIRS (default ~/.claude; space-separated absolute
#               paths)
#
# Subcommands: status

set -euo pipefail

: "${CLAUDE_CONFIG_DIRS:=$HOME/.claude}"

pretty_path() {
    case "$1" in
        "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;;
        *)         printf '%s' "$1" ;;
    esac
}

is_listed() {
    local dir
    for dir in $CLAUDE_CONFIG_DIRS; do
        [ "${dir%/}" = "${1%/}" ] && return 0
    done
    return 1
}

cmd_status() {
    local dir found=0
    printf 'claude config dirs (CLAUDE_CONFIG_DIRS):\n'
    for dir in $CLAUDE_CONFIG_DIRS; do
        if [ -d "$dir" ]; then
            printf '%-50s OK managed\n' "$(pretty_path "$dir")"
        else
            printf '%-50s ! listed but not found\n' "$(pretty_path "$dir")"
        fi
    done
    for dir in "$HOME"/.claude "$HOME"/.claude-*; do
        [ -d "$dir" ] || continue
        is_listed "$dir" && continue
        found=1
        printf '%-50s ? not managed; add it to CLAUDE_CONFIG_DIRS in agents/local.mk\n' "$(pretty_path "$dir")"
    done
    [ "$found" = "1" ] || printf 'no other ~/.claude* dirs found\n'
    printf '\n'
}

case "${1:-}" in
    status) cmd_status ;;
    *) printf 'usage: %s status\n' "$0" >&2; exit 2 ;;
esac
