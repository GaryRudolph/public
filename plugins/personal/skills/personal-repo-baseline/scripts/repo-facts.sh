#!/usr/bin/env bash
# Facts for the personal-repo-baseline skill: what each repo has today for
# every baseline item. Read-only. Prints current file contents and GitHub
# settings and makes no recommendations: the agent compares them with
# templates/ and decides.
#
# Needs bash (3.2 is fine), git, and python3. gh is optional; without it, or
# without access, the GitHub section prints why it couldn't read anything.
#
# Usage: repo-facts.sh [<repo> ...]    (default: the current directory)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
merge_template="$here/../templates/github-merge-settings.json"
errf=$(mktemp)
trap 'rm -f "$errf"' EXIT

section() { printf '\n== %s\n' "$1"; }
indent() { sed 's/^/  /'; }

# The GitHub keys to read come from the template, so a key added there is
# read here too.
github_filter() {
    python3 -c '
import json, sys
keys = list(json.load(open(sys.argv[1])))
print("{" + ", ".join(["full_name", "permissions"] + keys) + "}")
' "$merge_template"
}

# owner/name from the last two path parts of a remote URL, in any form git
# or the cloud proxy uses: https://github.com/o/r(.git), git@github.com:o/r,
# ssh://git@github.com/o/r, http://local_proxy@127.0.0.1:1234/git/o/r
slug_from_url() {
    python3 -c '
import re, sys
m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", sys.argv[1])
print(m.group(1) + "/" + m.group(2) if m else "")
' "$1"
}

# Prints "yes" or "no: <parser error>", then any duplicate keys (a later
# duplicate silently replaces an earlier one in most parsers).
json_facts() {
    python3 -c '
import json, sys
dupes = []
def hook(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            dupes.append(k)
        seen.add(k)
    return dict(pairs)
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"), object_pairs_hook=hook)
except ValueError as exc:
    print("parses: no: %s" % exc)
    sys.exit(0)
print("parses: yes")
names = {dict: "object", list: "array", str: "string", bool: "boolean", int: "number", float: "number", type(None): "null"}
print("top-level type: %s" % names[type(data)])
if isinstance(data, dict):
    print("top-level keys: %s" % (", ".join(data) or "(none)"))
print("duplicate keys: %s" % (", ".join(dupes) or "none"))
if len(sys.argv) > 2 and isinstance(data, dict):
    for key in sys.argv[2:]:
        if key in data:
            print("%s: %s" % (key, json.dumps(data[key])))
' "$@"
}

facts_for() {
    local dir="$1" root slug origin branch
    printf '\n### %s\n' "$dir"

    section repo
    if root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null); then
        origin=$(git -C "$root" remote get-url origin 2>/dev/null || true)
        slug=""
        [ -n "$origin" ] && slug=$(slug_from_url "$origin")
        printf '  root: %s\n' "$root"
        printf '  origin: %s\n' "${origin:-none}"
        printf '  owner/name from origin: %s\n' "${slug:-none}"
        branch=$(git -C "$root" branch --show-current 2>/dev/null || true)
        printf '  branch: %s\n' "${branch:-none (detached HEAD)}"
        printf '  commits on HEAD: %s\n' "$(git -C "$root" rev-list --count HEAD 2>/dev/null || echo 0)"
    else
        root=$(cd "$dir" && pwd)
        slug=""
        printf '  root: %s (not a git repository)\n' "$root"
    fi

    local f="$root/.claude/settings.json"
    section ".claude/settings.json"
    if [ -f "$f" ]; then
        printf '  present: yes\n'
        if git -C "$root" ls-files --error-unmatch .claude/settings.json >/dev/null 2>&1; then
            printf '  tracked by git: yes\n'
        else
            printf '  tracked by git: no\n'
        fi
        json_facts "$f" | indent
        printf '  contents:\n'
        sed 's/^/    | /' "$f"
    else
        printf '  present: no\n'
    fi

    # Local settings override the shared file on this machine. Only key names
    # and the attribution value are printed: the rest may be personal.
    local lf="$root/.claude/settings.local.json"
    section ".claude/settings.local.json"
    if [ -f "$lf" ]; then
        printf '  present: yes\n'
        if git -C "$root" check-ignore -q .claude/settings.local.json 2>/dev/null; then
            printf '  ignored by git: yes\n'
        else
            printf '  ignored by git: no\n'
        fi
        json_facts "$lf" attribution includeCoAuthoredBy | indent
    else
        printf '  present: no\n'
    fi

    section "GitHub merge settings"
    if ! command -v gh >/dev/null 2>&1; then
        printf '  gh: missing\n'
    elif [ -z "$slug" ]; then
        printf '  gh: %s\n' "$(gh --version 2>/dev/null | head -1)"
        printf '  not read: no origin remote to name the repo\n'
    else
        printf '  gh: %s\n' "$(gh --version 2>/dev/null | head -1)"
        printf '  request: gh api repos/%s\n' "$slug"
        local out rc
        out=$(gh api "repos/$slug" --jq "$(github_filter)" 2>"$errf")
        rc=$?
        if [ "$rc" -eq 0 ]; then
            printf '%s\n' "$out" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))' | indent
        else
            printf '  failed (exit %s): %s\n' "$rc" "$(head -3 "$errf" | tr '\n' ' ')"
        fi
    fi
}

for t in git python3; do
    command -v "$t" >/dev/null 2>&1 || { echo "repo-facts: $t is required" >&2; exit 2; }
done

if [ "$#" -eq 0 ]; then
    set -- .
fi
for dir in "$@"; do
    if [ -d "$dir" ]; then
        facts_for "$dir"
    else
        printf '\n### %s\n  not a directory\n' "$dir"
    fi
done
