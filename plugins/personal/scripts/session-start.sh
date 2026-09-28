#!/usr/bin/env bash
# SessionStart hook for the `personal` plugin. Prints one part of the
# always-on core standards so every Claude Code session gets them, including
# cloud and self-hosted runner sessions that never see ~/.claude/CLAUDE.md.
#
# Plain stdout from a SessionStart hook becomes context for Claude.

set -euo pipefail

root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
skill_dir="$root/skills/personal-standards"
core="$skill_dir/core.md"
[ -f "$core" ] || exit 0

# On Gary's workstation `make install` already @-imports core.md from
# ~/.claude/CLAUDE.md. Injecting it again would only duplicate it.
user_memory="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/CLAUDE.md"
if [ -f "$user_memory" ] && grep -qF '# >>> personal >>>' "$user_memory"; then
    exit 0
fi

# Claude Code caps each hook's stdout at 10,000 characters and swaps anything
# longer for a 2,000-character preview. core.md is longer than that, so
# hooks.json runs this script once per part and each run prints one slice,
# cut on line boundaries.
part="${1:-1}"
max_chars=9000

awk -v part="$part" -v max="$max_chars" -v dir="$skill_dir" '
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
' "$core"
