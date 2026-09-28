#!/usr/bin/env bash
# Facts for the personal-handoff skill. Prints what the agent needs to name
# and fill a handoff or plan file. Emits no verdicts: the agent picks the
# topic and writes the contents.

set -uo pipefail

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$root" || exit 1

printf 'repo_root: %s\n' "$root"
printf 'branch: %s\n' "$(git branch --show-current 2>/dev/null || echo '(not a git repo)')"
printf 'has_specs_dir: %s\n' "$([ -d specs ] && echo yes || echo no)"

if [ -d .scratch ]; then
    printf 'scratch_dir: exists\n'
else
    printf 'scratch_dir: missing\n'
fi
if git check-ignore -q .scratch/probe 2>/dev/null; then
    printf 'scratch_ignored: yes\n'
else
    printf 'scratch_ignored: no\n'
fi

printf '\nexisting handoff and plan files:\n'
find .scratch specs/handoffs -maxdepth 1 -type f \
    \( -name 'handoff-*.md' -o -name 'plan-*.md' \) 2>/dev/null | sort | sed 's/^/  /'

printf '\nworking tree changes:\n'
git status --short 2>/dev/null | sed 's/^/  /'

printf '\nrecent commits:\n'
git log --oneline -10 2>/dev/null | sed 's/^/  /'

# Suggest a {word} that no existing handoff or plan file uses yet.
words=(meadow harbor quartz cedar ember falcon glacier juniper lantern
       marble nimbus orchid pebble quill raven saffron timber willow zephyr
       basalt canyon delta fern garnet heron iris kestrel lagoon mosaic)
taken=$(find .scratch -maxdepth 1 -type f -name '*.md' 2>/dev/null | sed 's/.*-//; s/\.md$//')
start=$((RANDOM % ${#words[@]}))
for i in $(seq 0 $((${#words[@]} - 1))); do
    w=${words[$(((start + i) % ${#words[@]}))]}
    if ! printf '%s\n' "$taken" | grep -qx "$w"; then
        printf '\nsuggested_word: %s\n' "$w"
        exit 0
    fi
done
printf '\nsuggested_word: %s\n' "$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
