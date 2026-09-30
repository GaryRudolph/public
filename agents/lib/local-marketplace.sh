#!/usr/bin/env bash
# Register this checkout as a local Claude Code plugin marketplace, for people
# who edit this repo. A marketplace added from a directory loads its plugins in
# place, so edits apply at the next session start without a push. Everyone
# else gets the plugins from claude.ai (organization sync or their account) and doesn't
# need this.
#
# Ownership: the marketplace is ours only when its source directory is this
# checkout. uninstall leaves a marketplace named $MARKETPLACE alone if it
# points anywhere else (another checkout, or GitHub).
#
# Required env: REPO_DIR, MARKETPLACE, PLUGINS (space-separated plugin names)
#
# Subcommands: install | uninstall | status | dry-run

set -euo pipefail

: "${REPO_DIR:?REPO_DIR must be set}"
: "${MARKETPLACE:?MARKETPLACE must be set}"
: "${PLUGINS:?PLUGINS must be set}"
: "${CLAUDE_BIN:=claude}"

DRY_RUN=0

have_claude() {
    command -v "$CLAUDE_BIN" >/dev/null 2>&1
}

# Prints the directory our marketplace name points at, or nothing.
marketplace_path() {
    "$CLAUDE_BIN" plugin marketplace list --json 2>/dev/null | python3 -c '
import json, sys
name = sys.argv[1]
try:
    entries = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for e in entries:
    if e.get("name") == name:
        print(e.get("path") or e.get("installLocation") or "")
' "$MARKETPLACE" || true
}

installed_plugins() {
    "$CLAUDE_BIN" plugin list --json 2>/dev/null | python3 -c '
import json, sys
suffix = "@" + sys.argv[1]
try:
    entries = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for e in entries:
    if e.get("id", "").endswith(suffix):
        print(e["id"])
' "$MARKETPLACE" || true
}

same_dir() {
    [ -n "$1" ] && [ -d "$1" ] && [ "$(cd "$1" && pwd -P)" = "$(cd "$2" && pwd -P)" ]
}

run() {
    if [ "$DRY_RUN" = "1" ]; then
        printf '  would run: %s\n' "$*"
    else
        "$@"
    fi
}

cmd_install() {
    have_claude || { printf 'local-marketplace: %s not on PATH; skipping\n' "$CLAUDE_BIN"; return 0; }
    local current
    current=$(marketplace_path)
    if [ -n "$current" ] && ! same_dir "$current" "$REPO_DIR"; then
        printf 'local-marketplace: %s already points at %s; leaving it\n' "$MARKETPLACE" "$current" >&2
        printf '  remove it first: %s plugin marketplace remove %s\n' "$CLAUDE_BIN" "$MARKETPLACE" >&2
        return 1
    fi
    [ -n "$current" ] || run "$CLAUDE_BIN" plugin marketplace add "$REPO_DIR"
    local p installed
    installed=$(installed_plugins)
    for p in $PLUGINS; do
        if printf '%s\n' "$installed" | grep -qxF "$p@$MARKETPLACE"; then
            printf 'local-marketplace: %s@%s already installed\n' "$p" "$MARKETPLACE"
        else
            run "$CLAUDE_BIN" plugin install "$p@$MARKETPLACE" --scope user
        fi
    done
}

cmd_uninstall() {
    have_claude || return 0
    local current
    current=$(marketplace_path)
    [ -n "$current" ] || return 0
    if ! same_dir "$current" "$REPO_DIR"; then
        printf 'local-marketplace: %s points at %s, not this checkout; leaving it\n' "$MARKETPLACE" "$current"
        return 0
    fi
    local p
    for p in $(installed_plugins); do
        run "$CLAUDE_BIN" plugin uninstall "$p"
    done
    run "$CLAUDE_BIN" plugin marketplace remove "$MARKETPLACE"
}

cmd_status() {
    if ! have_claude; then
        printf 'local-marketplace: %s not on PATH\n' "$CLAUDE_BIN"
        return 0
    fi
    local current
    current=$(marketplace_path)
    if [ -z "$current" ]; then
        printf 'local-marketplace: not registered (plugins come from org sync, if enabled)\n'
    elif same_dir "$current" "$REPO_DIR"; then
        printf 'local-marketplace: %s -> this checkout; installed: %s\n' "$MARKETPLACE" "$(installed_plugins | tr '\n' ' ')"
    else
        printf 'local-marketplace: %s -> %s (not this checkout)\n' "$MARKETPLACE" "$current"
    fi
}

case "${1:-}" in
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    dry-run)   DRY_RUN=1; cmd_install ;;
    status)    cmd_status ;;
    *) printf 'usage: %s {install|uninstall|dry-run|status}\n' "$0" >&2; exit 2 ;;
esac
