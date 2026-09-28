#!/usr/bin/env bash
# SessionStart hook for the `personal` plugin. Prints one part of the
# always-on core standards so every session gets them, including cloud and
# self-hosted runner sessions that never see the home-directory blocks.
#
# The same hooks/hooks.json serves Claude Code, Codex, and Gemini CLI:
#   Claude Code, Codex  plain stdout becomes context
#   Gemini CLI          stdout must be one JSON object, nothing else

set -euo pipefail

if [ -n "${PLUGIN_ROOT:-}" ]; then
    tool=codex
    home_file="${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
elif [ -n "${GEMINI_PROJECT_DIR:-}" ] && [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    tool=gemini
    home_file="$HOME/.gemini/GEMINI.md"
else
    tool=claude
    home_file="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/CLAUDE.md"
fi

# Gemini treats empty or non-JSON stdout as a failed hook.
finish_silently() {
    [ "$tool" = "gemini" ] && printf '{}\n'
    exit 0
}

root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}}"
skill_dir="$root/skills/personal-standards"
core="$skill_dir/core.md"
[ -f "$core" ] || finish_silently

# On Gary's workstation `make install` already puts core.md in each tool's
# home file. Injecting it again would only duplicate it.
if [ -f "$home_file" ] && grep -qF '# >>> personal >>>' "$home_file"; then
    finish_silently
fi

# Claude Code caps each hook's stdout at 10,000 characters and swaps anything
# longer for a 2,000-character preview. core.md is longer than that, so
# hooks.json runs this script once per part and each run prints one slice,
# cut on line boundaries.
part="${1:-1}"
max_chars=9000

text=$(awk -v part="$part" -v max="$max_chars" -v dir="$skill_dir" '
    BEGIN { n = 1; size = 0 }
    {
        len = length($0) + 1
        if (size > 0 && size + len > max) { n++; size = 0 }
        size += len
        text[n] = text[n] $0 "\n"
    }
    END {
        if (part > n) exit
        printf "Gary Rudolph'"'"'s personal standards, part %d of %d, loaded by the personal plugin.\n", part, n
        if (part == 1) {
            printf "Wherever they cite ~/Projects/personal/public/standards/<file> and that path\n"
            printf "does not exist on this machine, read %s/standards/<file> instead.\n", dir
        }
        printf "\n%s", text[part]
    }
' "$core")

[ -n "$text" ] || finish_silently

if [ "$tool" = "gemini" ]; then
    command -v python3 >/dev/null 2>&1 || finish_silently
    TEXT="$text" python3 -c 'import json, os; print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": os.environ["TEXT"]}}))'
else
    printf '%s\n' "$text"
fi
