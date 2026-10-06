#!/usr/bin/env bash
# Facts for the personal-repo-baseline skill: what each repo has today for
# every baseline item. Read-only. Prints current file contents and GitHub
# settings and makes no recommendations: the agent compares them with
# templates/ and decides.
#
# Needs bash (3.2 is fine), git, and python3. gh is optional; without it, or
# without access, the GitHub section prints why it couldn't read anything.
# GitHub is read only when origin is github.com, Claude Code's cloud git
# proxy, or an ssh alias: on any other host, repos/<owner>/<name> on GitHub
# would be some other repo.
#
# Usage: repo-facts.sh [<repo> ...]    (default: the current directory)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
merge_template="$here/../templates/github-merge-settings.json"
errf=$(mktemp)
ghf=$(mktemp)
trap 'rm -f "$errf" "$ghf"' EXIT

section() { printf '\n== %s\n' "$1"; }
indent() { sed 's/^/  /'; }

# The GitHub keys to read come from the template, so a key added there is
# read here too.
github_filter() {
    python3 -c '
import json, sys
keys = list(json.load(open(sys.argv[1])))
print("{" + ", ".join(["full_name", "default_branch", "permissions"] + keys) + "}")
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

# "<host> <form>" for a remote URL. form is github (github.com), proxy
# (Claude Code's cloud git proxy, http://...@127.0.0.1:<port>/git/o/r),
# alias (an ssh host with no dot, such as a ~/.ssh/config Host entry),
# other, or local (a path or file:// URL, printed as "- local").
origin_host() {
    python3 -c '
import re, sys
url = sys.argv[1]
m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://(?:[^@/]*@)?(\[[^\]]*\]|[^:/]*)(?::[0-9]*)?(/.*)?$", url)
if m:
    scheme, host, path = m.group(1).lower(), m.group(2).lower(), m.group(3) or ""
    is_ssh = "ssh" in scheme
else:
    m = re.match(r"^(?:[^@/:]+@)?([^/:]+):", url)
    scheme, host, path, is_ssh = "scp", (m.group(1).lower() if m else ""), "", True
if not host or scheme == "file":
    print("- local")
elif host in ("github.com", "www.github.com", "ssh.github.com"):
    print(host, "github")
elif scheme in ("http", "https") and host in ("127.0.0.1", "localhost") and path.startswith("/git/"):
    print(host, "proxy")
elif is_ssh and "." not in host and host != "localhost":
    print(host, "alias")
else:
    print(host, "other")
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

# Compares the working-tree file at <path> with <rev>: prints same,
# differs, absent (not on <rev>), or norev (<rev> doesn't resolve here).
compare_to() {
    local root="$1" rev="$2" path="$3"
    if ! git -C "$root" rev-parse --verify --quiet "$rev^{commit}" >/dev/null 2>&1; then
        echo norev
    elif ! git -C "$root" cat-file -e "$rev:$path" 2>/dev/null; then
        echo absent
    elif git -C "$root" diff --quiet "$rev" -- "$path" 2>/dev/null; then
        echo same
    else
        echo differs
    fi
}

# Reads GitHub's settings into $ghf (printed later, as the last section)
# and sets gh_default to GitHub's default branch, if it said.
read_github() {
    local slug="$1" host="$2" form="$3" out rc
    gh_default=""
    : > "$ghf"
    if ! command -v gh >/dev/null 2>&1; then
        printf '  gh: missing\n' >> "$ghf"
        return
    fi
    printf '  gh: %s\n' "$(gh --version 2>/dev/null | head -1)" >> "$ghf"
    if [ -z "$slug" ]; then
        printf '  not read: no origin remote to name the repo\n' >> "$ghf"
        return
    fi
    case "$form" in
        github|proxy|alias) ;;
        local)
            printf '  not read: origin is a local path, not GitHub\n' >> "$ghf"
            return ;;
        *)
            printf "  not read: origin host %s isn't github.com, the cloud git proxy, or an ssh alias\n" "$host" >> "$ghf"
            return ;;
    esac
    printf '  request: gh api repos/%s\n' "$slug" >> "$ghf"
    out=$(gh api "repos/$slug" --jq "$(github_filter)" 2>"$errf")
    rc=$?
    if [ "$rc" -eq 0 ]; then
        printf '%s\n' "$out" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))' | indent >> "$ghf"
        gh_default=$(printf '%s\n' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("default_branch") or "")' 2>/dev/null)
    else
        printf '  failed (exit %s): %s\n' "$rc" "$(head -3 "$errf" | tr '\n' ' ')" >> "$ghf"
    fi
}

facts_for() {
    local dir="$1" root slug="" origin="" branch host="" form="" is_git=no line
    printf '\n### %s\n' "$dir"

    section repo
    if root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null); then
        is_git=yes
        origin=$(git -C "$root" remote get-url origin 2>/dev/null || true)
        if [ -n "$origin" ]; then
            slug=$(slug_from_url "$origin")
            read -r host form <<<"$(origin_host "$origin")"
        fi
        printf '  root: %s\n' "$root"
        printf '  origin: %s\n' "${origin:-none}"
        case "$form" in
            "") ;;
            local) printf '  origin host: none (local path)\n' ;;
            proxy) printf '  origin host: %s (Claude Code cloud git proxy)\n' "$host" ;;
            alias) printf '  origin host: %s (ssh alias)\n' "$host" ;;
            *) printf '  origin host: %s\n' "$host" ;;
        esac
        printf '  owner/name from origin: %s\n' "${slug:-none}"
        branch=$(git -C "$root" branch --show-current 2>/dev/null || true)
        printf '  branch: %s\n' "${branch:-none (detached HEAD)}"
        printf '  commits on HEAD: %s\n' "$(git -C "$root" rev-list --count HEAD 2>/dev/null || echo 0)"
    else
        root=$(cd "$dir" && pwd)
        printf '  root: %s (not a git repository)\n' "$root"
    fi

    # GitHub is read now, since its default branch feeds the settings.json
    # facts, and printed last.
    read_github "$slug" "$host" "$form"

    local rel=.claude/settings.json
    local f="$root/$rel"
    section "$rel"
    if [ -f "$f" ]; then
        printf '  present: yes\n'
        if [ -L "$f" ]; then
            printf '  symlink to: %s\n' "$(readlink "$f")"
        fi
        if [ "$is_git" = yes ]; then
            if git -C "$root" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
                printf '  tracked by git: yes\n'
            else
                printf '  tracked by git: no\n'
            fi
            case "$(compare_to "$root" HEAD "$rel")" in
                same) printf '  differs from HEAD: no\n' ;;
                differs) printf '  differs from HEAD: yes\n' ;;
                absent) printf '  differs from HEAD: yes (not in HEAD)\n' ;;
                *) printf '  differs from HEAD: unknown (no commits)\n' ;;
            esac
            local def
            def=$(git -C "$root" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
            if [ -n "$def" ]; then
                printf '  origin default branch: %s (local origin/HEAD)\n' "$def"
            elif [ -n "$gh_default" ]; then
                def="origin/$gh_default"
                printf '  origin default branch: %s (GitHub default_branch)\n' "$def"
            else
                printf "  origin default branch: unknown (no local origin/HEAD, and GitHub didn't say)\n"
            fi
            if [ -n "$def" ]; then
                case "$(compare_to "$root" "$def" "$rel")" in
                    same) printf '  same as %s (as of the last fetch): yes\n' "$def" ;;
                    differs) printf '  same as %s (as of the last fetch): no\n' "$def" ;;
                    absent) printf '  same as %s (as of the last fetch): no (not on %s)\n' "$def" "$def" ;;
                    *) printf '  same as %s: unknown (no local %s; fetch first)\n' "$def" "$def" ;;
                esac
            fi
        else
            printf '  tracked by git: no (not a git repository)\n'
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
    while IFS= read -r line; do printf '%s\n' "$line"; done < "$ghf"
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
