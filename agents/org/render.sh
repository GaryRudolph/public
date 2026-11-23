#!/usr/bin/env bash
# Render the Claude Code managed settings that get pasted into each org's
# claude.ai console (settings.json lists the orgs), from the canonical
# allowlist file and claude-managed-base.json:
#
#   render.sh render   write claude-managed-settings.json
#   render.sh check    exit 1 when the committed file is stale (make test)
#
# The permissions come from lib/allowlist.jq, the same rules the local
# installer writes. The base's other keys are merged under them, keys come out
# sorted, and the settings-commit stamp goes last, so the pasted text ends
# with it. The stamp stays a {{ commit }} placeholder here; the issue that
# carries the paste fills it in (settings_issue.py).
set -euo pipefail

ORG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(dirname "$ORG_DIR")"
: "${ALLOWLISTS_SRC:=$AGENTS_DIR/allowlists/personal.json}"
BASE="$ORG_DIR/claude-managed-base.json"
OUT="$ORG_DIR/claude-managed-settings.json"

command -v jq >/dev/null 2>&1 || { echo "render.sh: jq is required" >&2; exit 2; }

render() {
    jq -S "$(cat "$AGENTS_DIR/lib/allowlist.jq")"'
        (meta_check), claude_permissions' "$ALLOWLISTS_SRC" \
        | jq -S -s '.[0] * .[1]' "$BASE" - \
        | jq 'if has("settings-commit")
              then del(."settings-commit") + {"settings-commit": ."settings-commit"}
              else . end'
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
render > "$tmp"

case "${1:-}" in
    render)
        if [ -f "$OUT" ] && cmp -s "$tmp" "$OUT"; then
            echo "= agents/org/claude-managed-settings.json current"
        else
            cp "$tmp" "$OUT"
            echo "+ wrote agents/org/claude-managed-settings.json"
        fi
        ;;
    check)
        if [ -f "$OUT" ] && cmp -s "$tmp" "$OUT"; then
            echo "agents/org/claude-managed-settings.json is current"
        else
            echo "agents/org/claude-managed-settings.json is stale: run make -C agents/org render and commit it" >&2
            diff -u "$OUT" "$tmp" >&2 || true
            exit 1
        fi
        ;;
    *)
        echo "usage: render.sh render|check" >&2
        exit 2
        ;;
esac
