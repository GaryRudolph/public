#!/usr/bin/env bash
# Facts for the personal-repo-baseline skill: what each repo has today for
# every baseline item. Read-only. Prints current file contents and GitHub
# settings and makes no recommendations: the agent compares them with
# templates/ and decides.
#
# Needs bash (3.2 is fine), git, and python3 3.9 or newer (its embedded
# scripts must compile there: no backslash inside an f-string expression,
# no match statement, no X | Y annotations). gh is optional; without it, or
# without access, the GitHub section prints why it couldn't read anything.
# GitHub is read only when origin is github.com, Claude Code's cloud git
# proxy, or an ssh alias for github.com: on any other host,
# repos/<owner>/<name> on GitHub would be some other repo. The origin URL is
# parsed and masked by the plugin's scripts/origin.py (a path from this file;
# a skill copied out of the plugin has no such file, and the origin is then
# not shown, never printed raw). An ssh host is resolved with `ssh -G`;
# without ssh, a host with no dot or a github.com-<ctx> alias is taken as
# one, unresolved.
#
# Usage: repo-facts.sh [<repo> ...]    (default: the current directory)
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
origin_py="$(cd "$(dirname "$0")" && pwd -P)/../../../scripts/origin.py"
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
# Parses a remote URL with origin.py into o_class (github, ssh443, alias,
# proxy, other, local, none), o_host, o_owner, o_repo, o_transport and
# o_masked (credentials masked; the raw URL is never printed). o_class is
# "unavailable" when origin.py can't be run, and the rest stay empty.
read_origin() {
    local line
    o_class=unavailable o_host="" o_owner="" o_repo="" o_transport="" o_masked=""
    [ -f "$origin_py" ] || return 0
    line=$(python3 -I "$origin_py" -- "$1" 2>/dev/null) || return 0
    IFS=$'\t' read -r o_class o_host o_owner o_repo o_transport o_masked <<<"$line"
    [ -n "$o_class" ] || { o_class=unavailable; return 0; }
    [ "$o_host" = "-" ] && o_host=""
    [ "$o_owner" = "-" ] && o_owner=""
    [ "$o_repo" = "-" ] && o_repo=""
    [ "$o_transport" = "-" ] && o_transport=""
    [ "$o_masked" = "-" ] && o_masked=""
    return 0
}

# The hostname ssh would connect to for an ssh host, after ~/.ssh/config
# Host entries (ssh -G reads the config and connects to nothing). Prints
# nothing when ssh is missing or doesn't say.
ssh_hostname() {
    case "$1" in -*) return 0 ;; esac
    command -v ssh >/dev/null 2>&1 || return 0
    ssh -G -- "$1" </dev/null 2>/dev/null | awk '$1 == "hostname" { print tolower($2); exit }'
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
# Hashes the file itself, so the index (a git rm --cached, say) doesn't
# change the answer; a symlink hashes as its target path, as git stores it.
compare_to() {
    local root="$1" rev="$2" path="$3" want have
    if ! git -C "$root" rev-parse --verify --quiet "$rev^{commit}" >/dev/null 2>&1; then
        echo norev
        return
    fi
    if ! want=$(git -C "$root" rev-parse --verify --quiet "$rev:$path" 2>/dev/null); then
        echo absent
        return
    fi
    if [ -L "$root/$path" ]; then
        have=$(printf '%s' "$(readlink "$root/$path")" | git -C "$root" hash-object --stdin 2>/dev/null)
    else
        have=$(git -C "$root" hash-object -- "$path" 2>/dev/null)
    fi
    if [ -n "$have" ] && [ "$have" = "$want" ]; then
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
    if [ "$form" = unavailable ]; then
        printf '  not read: origin.py unavailable\n' >> "$ghf"
        return
    fi
    if [ "$form" = local ]; then
        printf '  not read: origin is a local path, not GitHub\n' >> "$ghf"
        return
    fi
    if [ -z "$slug" ]; then
        printf '  not read: no origin remote to name the repo\n' >> "$ghf"
        return
    fi
    case "$form" in
        github|proxy|alias|unresolved) ;;
        *)
            printf "  not read: origin host %s isn't github.com, the cloud git proxy, or an ssh alias for github.com\n" "$host" >> "$ghf"
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

# True for a dotted-quad IPv4 address (four octets, 0-255, no leading zeros).
is_ipv4() {
    local octet='(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])'
    [[ "$1" =~ ^$octet\.$octet\.$octet\.$octet$ ]]
}

# Sets form and note for an ssh host: alias when ssh -G resolves it to
# GitHub, other when it resolves elsewhere, and, when it can't be resolved,
# unresolved for a host with no dot or a dotless github.com-<ctx> alias
# (also when ssh -G echoes it back with no Host entry), else other.
classify_ssh_host() {
    local host="$1" resolved
    resolved=$(ssh_hostname "$host")
    case "$resolved" in
        github.com|www.github.com|ssh.github.com)
            form=alias note="ssh alias for $resolved" ;;
        "")
            if command -v ssh >/dev/null 2>&1; then
                note="ssh alias, not resolved: ssh -G gave no hostname"
            else
                note="ssh alias, not resolved: no ssh"
            fi
            case "$host" in
                github.com-*.*) form=other note="" ;;
                github.com-*) form=unresolved ;;
                *.*) form=other note="" ;;
                *) form=unresolved ;;
            esac ;;
        "$host")
            case "$host" in
                github.com-*.*) form=other note="" ;;
                github.com-*) form=unresolved note="ssh alias, not resolved: no Host entry" ;;
                *) form=other note="" ;;
            esac ;;
        *) form=other note="ssh -G hostname $resolved" ;;
    esac
}

facts_for() {
    local dir="$1" root slug="" origin="" branch host="" form="" note="" is_git=no line
    printf '\n### %s\n' "$dir"

    section repo
    if root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null); then
        is_git=yes
        origin=$(git -C "$root" remote get-url origin 2>/dev/null || true)
        if [ -n "$origin" ]; then
            read_origin "$origin"
            host=$o_host
            [ -n "$o_owner" ] && [ -n "$o_repo" ] && slug="$o_owner/$o_repo"
            case "$o_class" in
                unavailable) form=unavailable host=unknown ;;
                github|ssh443) form=github ;;
                proxy) form=proxy note="Claude Code cloud git proxy" ;;
                alias) form=ssh; classify_ssh_host "$host" ;;
                local) form=local ;;
                *)
                    # Another ssh host may be a ~/.ssh/config alias for GitHub;
                    # an IP address or localhost is not.
                    case "$host" in
                        localhost|\[*|*:*) form=other ;;
                        *)
                            if is_ipv4 "$host"; then form=other
                            elif [ "$o_transport" = ssh ]; then form=ssh; classify_ssh_host "$host"
                            else form=other
                            fi ;;
                    esac ;;
            esac
        fi
        printf '  root: %s\n' "$root"
        if [ -z "$origin" ]; then
            printf '  origin: none\n'
        elif [ "$form" = unavailable ]; then
            printf '  origin: not shown (origin.py unavailable at %s)\n' "$origin_py"
        else
            printf '  origin: %s\n' "$o_masked"
        fi
        case "$form" in
            "") ;;
            unavailable) printf '  origin host: unknown (origin.py unavailable)\n' ;;
            local) printf '  origin host: none (local path)\n' ;;
            *) printf '  origin host: %s%s\n' "$host" "${note:+ ($note)}" ;;
        esac
        if [ "$form" = unavailable ]; then
            printf '  owner/name from origin: unknown\n'
        else
            printf '  owner/name from origin: %s\n' "${slug:-none}"
        fi
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

    # The PR template GitHub's web form fills in, for people and tools the
    # plugin doesn't reach. Printed verbatim; the agent compares it with
    # templates/pull_request_template.md. Python, not find or grep: the
    # tests run this with a minimal PATH.
    section "PR template"
    python3 - "$root" <<'PY'
import os, re, sys
root = sys.argv[1]
found = []
for d in ("", ".github", "docs"):
    full = os.path.join(root, d)
    if os.path.isdir(full):
        found += [os.path.join(d, n) for n in sorted(os.listdir(full))
                  if n.lower() == "pull_request_template.md" and os.path.isfile(os.path.join(full, n))]
folder = os.path.join(root, ".github", "PULL_REQUEST_TEMPLATE")
for rel in found:
    text = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
    print(f"  path: {rel}")
    has_guide = "yes" if re.search(r"^##[ \t]+Review guide[ \t]*$", text, re.M | re.I) else "no"
    has_tier = "yes" if re.search(r"Review tier:", text, re.I) else "no"
    print(f"  has ## Review guide: {has_guide}")
    print(f"  has Review tier: line: {has_tier}")
    print("  contents:")
    for line in text.splitlines():
        print(f"    | {line}")
if os.path.isdir(folder):
    print(f"  template folder: .github/PULL_REQUEST_TEMPLATE/ ({', '.join(sorted(os.listdir(folder)))})")
if not found and not os.path.isdir(folder):
    print("  present: no")
PY

    # Copilot's code review reads the repo's instructions, never the plugin.
    # Printed verbatim; the agent compares it with
    # templates/copilot-instructions.md.
    section "Copilot instructions"
    python3 - "$root" <<'PY'
import os, re, sys
path = os.path.join(sys.argv[1], ".github", "copilot-instructions.md")
if os.path.isfile(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    print("  path: .github/copilot-instructions.md")
    has_heading = "yes" if re.search(r"^#+[ \t]+Code review[ \t]*$", text, re.M | re.I) else "no"
    has_label = "yes" if "blocking:" in text else "no"
    print(f"  has Code review heading: {has_heading}")
    print(f"  has blocking: label: {has_label}")
    print("  contents:")
    for line in text.splitlines():
        print(f"    | {line}")
else:
    print("  present: no")
PY

    # Workflows and the lines that decide whether they run on a draft PR:
    # the trigger, its types, and any draft test. The agent reads them
    # (and the file, when it's unclear) and decides.
    section "Workflows on pull requests"
    python3 - "$root" <<'PY'
import os, re, sys
root = sys.argv[1]
folder = os.path.join(root, ".github", "workflows")
names = sorted(n for n in os.listdir(folder)
               if n.endswith((".yml", ".yaml"))
               and os.path.isfile(os.path.join(folder, n))) if os.path.isdir(folder) else []
if not names:
    print("  workflows: none")
pattern = re.compile(r"pull_request|types|draft|ready_for_review")
for name in names:
    lines = open(os.path.join(folder, name), encoding="utf-8", errors="replace").read().splitlines()
    print(f"  path: .github/workflows/{name}")
    print(f"  mentions pull_request: {'yes' if any('pull_request' in l for l in lines) else 'no'}")
    for number, line in enumerate(lines, 1):
        if pattern.search(line) and not line.lstrip().startswith("#"):
            print(f"    {number}: {line.strip()}")
PY

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
