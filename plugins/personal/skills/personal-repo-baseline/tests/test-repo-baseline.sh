#!/usr/bin/env bash
# Tests for scripts/merge_settings.py and scripts/repo-facts.sh against
# fixture repos, with a stub gh. Needs only bash, git, and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
merge="$here/../scripts/merge_settings.py"
facts="$here/../scripts/repo-facts.sh"
tmpl="$here/../templates/claude-settings.json"
gh_tmpl="$here/../templates/github-merge-settings.json"
bash_bin=$(command -v bash)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
run()  { "$@" >"$work/out" 2>"$work/err"; }
expect_ok()   { local d="$1"; shift; if run "$@"; then pass "$d"; else fail "$d (exit $?)"; sed 's/^/        /' "$work/err" >&2; fi; }
expect_rc()   { local d="$1" want="$2"; shift 2; run "$@"; local rc=$?; if [ "$rc" = "$want" ]; then pass "$d"; else fail "$d: exit $rc, expected $want"; fi; }
expect_eq()   { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1: expected '$3', got '$2'"; fi; }
expect_grep() { if grep -qF -- "$3" "$work/$2"; then pass "$1"; else fail "$1: no '$3' in $2"; sed 's/^/        /' "$work/$2" >&2; fi; }
expect_nogrep() { if grep -qF -- "$3" "$work/$2"; then fail "$1: '$3' in $2"; else pass "$1"; fi; }
jget() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d[k]
print(json.dumps(d))' "$1" "$2"; }
first_key() { python3 -c 'import json,sys; print(next(iter(json.load(open(sys.argv[1])))))' "$1"; }

printf 'templates\n'
expect_ok "claude-settings.json parses"          python3 -m json.tool "$tmpl"
expect_ok "github-merge-settings.json parses"    python3 -m json.tool "$gh_tmpl"
expect_eq "\$schema comes first"                 "$(first_key "$tmpl")" '$schema'

printf 'merge_settings.py\n'
t="$work/new/.claude/settings.json"
expect_ok "missing target: dry run succeeds"     python3 "$merge" "$tmpl" "$t"
expect_eq "  ...writes nothing"                  "$(test -e "$t" && echo exists || echo absent)" absent
expect_ok "missing target: write"                python3 "$merge" "$tmpl" "$t" --write
if cmp -s "$tmpl" "$t"; then pass "  ...file equals the template"; else fail "  ...file differs from the template"; fi

t="$work/existing.json"
cat > "$t" <<'EOF'
{
    "permissions": {"allow": ["Bash(make test)"], "deny": ["Read(./.env)"]},
    "env": {"NOTE": "café"}
}
EOF
snap=$(cat "$t")
expect_ok "existing file: dry run"               python3 "$merge" "$tmpl" "$t"
expect_eq "  ...changes nothing"                 "$(cat "$t")" "$snap"
expect_ok "existing file: --diff"                python3 "$merge" "$tmpl" "$t" --diff
expect_grep "  ...diff adds attribution"         out '+  "attribution": {'
expect_eq "  ...still changes nothing"           "$(cat "$t")" "$snap"
expect_ok "existing file: write"                 python3 "$merge" "$tmpl" "$t" --write
expect_eq "  ...permissions kept"                "$(jget "$t" permissions)" '{"allow": ["Bash(make test)"], "deny": ["Read(./.env)"]}'
expect_eq "  ...env kept, non-ASCII intact"      "$(grep -c 'café' "$t")" 1
expect_eq "  ...attribution.commit added"        "$(jget "$t" attribution.commit)" '"Assisted-by: Claude Code"'
expect_eq "  ...\$schema first"                  "$(first_key "$t")" '$schema'
expect_eq "  ...2-space indent"                  "$(sed -n 2p "$t")" '  "$schema": "https://json.schemastore.org/claude-code-settings.json",'
snap=$(cat "$t")
expect_ok "second write"                         python3 "$merge" "$tmpl" "$t" --write
expect_grep "  ...reports unchanged"             err "unchanged: $t"
expect_eq "  ...file identical"                  "$(cat "$t")" "$snap"

t="$work/conflict.json"
printf '{\n  "attribution": {"commit": null, "sessionUrl": true}\n}\n' > "$t"
chmod 600 "$t"
expect_ok "conflict: write without --take"       python3 "$merge" "$tmpl" "$t" --write
expect_grep "  ...lists the kept value"          err 'kept: attribution.commit: null (template: "Assisted-by: Claude Code")'
expect_eq "  ...kept value untouched"            "$(jget "$t" attribution.commit)" null
expect_eq "  ...missing sibling added"           "$(jget "$t" attribution.pr)" '"Assisted-by: Claude Code"'
expect_eq "  ...extra key kept"                  "$(jget "$t" attribution.sessionUrl)" true
expect_eq "  ...file mode kept"                  "$(python3 -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777))' "$t")" 0o600
expect_ok "conflict: --take attribution.commit"  python3 "$merge" "$tmpl" "$t" --write --take attribution.commit
expect_eq "  ...template value taken"            "$(jget "$t" attribution.commit)" '"Assisted-by: Claude Code"'
snap=$(cat "$t")
expect_rc "--take with nothing to take fails"    2 python3 "$merge" "$tmpl" "$t" --write --take attribution.nope
expect_eq "  ...file untouched"                  "$(cat "$t")" "$snap"

t="$work/compliant.json"
cat > "$t" <<'EOF2'
{
    "$schema": "https://json.schemastore.org/claude-code-settings.json",
    "permissions": {"allow": ["Bash(make test)"]},
    "attribution": {
        "pr": "Assisted-by: Claude Code",
        "commit": "Assisted-by: Claude Code"
    }
}
EOF2
cp "$t" "$work/compliant.orig"
expect_ok "reformat only: --diff"                python3 "$merge" "$tmpl" "$t" --diff
expect_grep "  ...reports unchanged"             err "unchanged: $t"
expect_eq "  ...prints no diff"                  "$(cat "$work/out")" ""
expect_ok "reformat only: write"                 python3 "$merge" "$tmpl" "$t" --write
expect_grep "  ...reports unchanged"             err "unchanged: $t"
if cmp -s "$t" "$work/compliant.orig"; then pass "  ...file byte for byte"; else fail "  ...file was rewritten"; fi

t="$work/schema-second.json"
printf '{"attribution": {"commit": "Assisted-by: Claude Code", "pr": "Assisted-by: Claude Code"}, "$schema": "https://json.schemastore.org/claude-code-settings.json"}\n' > "$t"
expect_ok "key order only: --diff"               python3 "$merge" "$tmpl" "$t" --diff
expect_grep "  ...\$schema move is a change"     err "would change: $t"

mkdir -p "$work/real" "$work/link/.claude"
printf '{"env": {"A": "1"}}\n' > "$work/real/settings.json"
ln -s "$work/real/settings.json" "$work/link/.claude/settings.json"
t="$work/link/.claude/settings.json"
expect_ok "symlinked target: write"              python3 "$merge" "$tmpl" "$t" --write
expect_eq "  ...link kept"                       "$(test -L "$t" && echo link || echo file)" link
expect_eq "  ...real file updated"               "$(jget "$work/real/settings.json" attribution.pr)" '"Assisted-by: Claude Code"'
expect_eq "  ...real file keeps its keys"        "$(jget "$work/real/settings.json" env.A)" '"1"'
expect_eq "  ...no temp file left"               "$(find "$work/link/.claude" "$work/real" -name '.merge_settings.*')" ""

for case in 'trailing-comma:{"a": 1,}' 'duplicate-keys:{"a": 1, "a": 2}' 'array:[1, 2]'; do
    name=${case%%:*}
    t="$work/bad-$name.json"
    printf '%s\n' "${case#*:}" > "$t"
    snap=$(cat "$t")
    expect_rc "bad input ($name) fails"          1 python3 "$merge" "$tmpl" "$t" --write
    expect_eq "  ...file untouched"              "$(cat "$t")" "$snap"
done

printf 'repo-facts.sh\n'
stub="$work/stub"
mkdir -p "$stub"
cat > "$stub/gh" <<'EOF'
#!/usr/bin/env bash
case "$1" in
    --version) echo "gh version 0.0.0-stub"; exit 0 ;;
    api)
        printf '%s\n' "$@" > "$GH_ARGS_FILE"
        if [ -n "${GH_STUB_FAIL:-}" ]; then
            echo "gh: Must have admin rights to Repository. (HTTP 403)" >&2
            exit 1
        fi
        echo '{"allow_merge_commit":true,"allow_squash_merge":true,"default_branch":"main","full_name":"acme/widget","permissions":{"admin":false}}'
        ;;
esac
EOF
# ssh -G -- <host> prints what ~/.ssh/config would resolve it to.
cat > "$stub/ssh" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -G ] || exit 255
shift
[ "$1" = -- ] && shift
printf '%s\n' "$1" >> "$SSH_ARGS_FILE"
case "$1" in
    github.com-lolay|github.com-agerpoint|gh-work) h=github.com ;;
    gl-work) h=gitlab.example.com ;;
    broken) exit 255 ;;
    *) h=$1 ;;
esac
printf 'user git\nhostname %s\nport 22\n' "$h"
EOF
chmod +x "$stub/gh" "$stub/ssh"
export GH_ARGS_FILE="$work/gh-args" SSH_ARGS_FILE="$work/ssh-args"

repo="$work/widget"
mkdir -p "$repo/.claude"
git -C "$repo" init -q
git -C "$repo" config user.email t@example.com
git -C "$repo" config user.name test
git -C "$repo" config commit.gpgsign false
git -C "$repo" remote add origin https://github.com/acme/widget.git
printf '{\n  "permissions": {"allow": []}\n}\n' > "$repo/.claude/settings.json"
printf '{"attribution": {"commit": ""}, "env": {"TOKEN": "s3cr3t-value"}}\n' > "$repo/.claude/settings.local.json"
printf '.claude/settings.local.json\n' > "$repo/.gitignore"
git -C "$repo" add -A && git -C "$repo" commit -qm init
snap=$(git -C "$repo" status --porcelain)

expect_ok "facts on a fixture repo"              env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
expect_grep "  ...owner/name from https origin"  out 'owner/name from origin: acme/widget'
expect_grep "  ...origin host"                   out 'origin host: github.com'
expect_grep "  ...settings.json tracked"         out 'tracked by git: yes'
expect_grep "  ...same as HEAD"                  out 'differs from HEAD: no'
expect_grep "  ...default branch from GitHub"    out 'origin default branch: origin/main (GitHub default_branch)'
expect_grep "  ...origin/main not fetched"       out 'same as origin/main: unknown (no local origin/main; fetch first)'
expect_grep "  ...settings.json contents"        out '    |   "permissions": {"allow": []}'
expect_grep "  ...local attribution value"       out 'attribution: {"commit": ""}'
expect_grep "  ...local file ignored by git"     out 'ignored by git: yes'
expect_nogrep "  ...local values otherwise hidden" out 's3cr3t-value'
expect_grep "  ...GitHub values printed"         out '"allow_merge_commit": true'
expect_grep "  ...request names the repo"        gh-args 'repos/acme/widget'
for key in full_name default_branch $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))))' "$gh_tmpl"); do
    expect_grep "  ...filter reads $key"         gh-args "$key"
done
expect_eq "  ...read-only"                       "$(git -C "$repo" status --porcelain)" "$snap"

git -C "$repo" update-ref refs/remotes/origin/main HEAD
git -C "$repo" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
expect_ok "local origin/HEAD"                    env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
expect_grep "  ...default branch from origin/HEAD" out 'origin default branch: origin/main (local origin/HEAD)'
expect_grep "  ...same as origin/main"           out 'same as origin/main (as of the last fetch): yes'
printf '{\n  "permissions": {"allow": ["Bash(ls)"]}\n}\n' > "$repo/.claude/settings.json"
expect_ok "settings.json edited, not committed"  env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
expect_grep "  ...differs from HEAD"             out 'differs from HEAD: yes'
expect_grep "  ...differs from origin/main"      out 'same as origin/main (as of the last fetch): no'
git -C "$repo" checkout -q -- .claude/settings.json
git -C "$repo" rm -q --cached .claude/settings.json
expect_ok "settings.json removed from the index" env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
expect_grep "  ...untracked"                     out 'tracked by git: no'
expect_grep "  ...still same as HEAD"            out 'differs from HEAD: no'
expect_grep "  ...still same as origin/main"     out 'same as origin/main (as of the last fetch): yes'
git -C "$repo" reset -q -- .claude/settings.json

expect_ok "gh refused"                           env PATH="$stub:$PATH" GH_STUB_FAIL=1 "$bash_bin" "$facts" "$repo"
expect_grep "  ...error reported"                out 'failed (exit 1): gh: Must have admin rights to Repository. (HTTP 403)'

nogh="$work/nogh"
mkdir -p "$nogh"
for t in git python3 sed head tr mktemp rm dirname; do ln -s "$(command -v "$t")" "$nogh/$t"; done
expect_ok "gh missing"                           env PATH="$nogh" "$bash_bin" "$facts" "$repo"
expect_grep "  ...says so"                       out 'gh: missing'

# PATH without ssh, for the unresolved-alias fallback.
nossh="$work/nossh"
mkdir -p "$nossh"
for t in bash git python3 sed head tr mktemp rm dirname awk readlink; do ln -s "$(command -v "$t")" "$nossh/$t"; done
ln -s "$stub/gh" "$nossh/gh"

# Each case: <ssh on PATH>|<url>|<origin host line>
for case in "yes|git@github.com:acme/widget.git|github.com" \
            "yes|ssh://git@github.com/acme/widget|github.com" \
            "yes|http://local_proxy@127.0.0.1:1234/git/acme/widget|127.0.0.1 (Claude Code cloud git proxy)" \
            "yes|git@github.com-lolay:acme/widget.git|github.com-lolay (ssh alias for github.com)" \
            "yes|ssh://git@github.com-agerpoint:22/acme/widget.git|github.com-agerpoint (ssh alias for github.com)" \
            "yes|git@gh-work:acme/widget.git|gh-work (ssh alias for github.com)" \
            "yes|git@broken:acme/widget.git|broken (ssh alias, not resolved: ssh -G gave no hostname)" \
            "no|git@github.com-agerpoint:acme/widget.git|github.com-agerpoint (ssh alias, not resolved: no ssh)" \
            "no|git@gh-work:acme/widget.git|gh-work (ssh alias, not resolved: no ssh)"; do
    has_ssh=${case%%|*} rest=${case#*|}
    url=${rest%%|*} want=${rest#*|}
    if [ "$has_ssh" = yes ]; then path="$stub:$PATH"; else path="$nossh"; fi
    git -C "$repo" remote set-url origin "$url"
    rm -f "$GH_ARGS_FILE"
    expect_ok "origin $url (ssh: $has_ssh)"      env PATH="$path" "$bash_bin" "$facts" "$repo"
    expect_grep "  ...owner/name parsed"         out 'owner/name from origin: acme/widget'
    expect_grep "  ...host"                      out "origin host: $want"
    expect_grep "  ...GitHub read"               gh-args 'repos/acme/widget'
done

for case in "yes|git@gitlab.com:acme/widget.git|gitlab.com" \
            "yes|https://gitlab.com/acme/widget.git|gitlab.com" \
            "yes|git@gl-work:acme/widget.git|gl-work (ssh -G hostname gitlab.example.com)" \
            "yes|git@github.com-nope:acme/widget.git|github.com-nope" \
            "yes|ssh://git@[::1]/acme/widget|[::1]" \
            "yes|git@[::1]:acme/widget.git|[::1]" \
            "no|git@gl.example.com:acme/widget.git|gl.example.com"; do
    has_ssh=${case%%|*} rest=${case#*|}
    url=${rest%%|*} want=${rest#*|}
    if [ "$has_ssh" = yes ]; then path="$stub:$PATH"; else path="$nossh"; fi
    git -C "$repo" remote set-url origin "$url"
    rm -f "$GH_ARGS_FILE" "$SSH_ARGS_FILE"
    expect_ok "origin $url (ssh: $has_ssh)"      env PATH="$path" "$bash_bin" "$facts" "$repo"
    expect_grep "  ...host"                      out "origin host: $want"
    expect_grep "  ...GitHub not read"           out "not read: origin host ${want%% (*} isn't github.com, the cloud git proxy, or an ssh alias for github.com"
    expect_eq "  ...gh not called"               "$(test -e "$GH_ARGS_FILE" && echo called || echo not)" not
    case "$want" in
        \[*) expect_eq "  ...ssh -G not run for an IP" "$(test -e "$SSH_ARGS_FILE" && echo called || echo not)" not ;;
    esac
done

for url in "$work/elsewhere/acme/widget.git" 'C:/repos/acme/widget.git' 'file:///srv/git/acme/widget.git'; do
    git -C "$repo" remote set-url origin "$url"
    rm -f "$GH_ARGS_FILE"
    expect_ok "origin $url"                      env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
    expect_grep "  ...host"                      out 'origin host: none (local path)'
    expect_grep "  ...GitHub not read"           out 'not read: origin is a local path, not GitHub'
    expect_eq "  ...gh not called"               "$(test -e "$GH_ARGS_FILE" && echo called || echo not)" not
done

# Each case: <url>|<origin line>
for case in 'https://gary:ghp_s3cr3t@github.com/acme/widget.git|https://***@github.com/acme/widget.git' \
            'https://ghp_s3cr3t@github.com/acme/widget.git|https://***@github.com/acme/widget.git' \
            'ssh://git:ghp_s3cr3t@github.com/acme/widget|ssh://git:***@github.com/acme/widget'; do
    url=${case%%|*}
    git -C "$repo" remote set-url origin "$url"
    expect_ok "credentials in origin"            env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
    expect_grep "  ...masked"                    out "origin: ${case#*|}"
    expect_nogrep "  ...secret not printed"      out 'ghp_s3cr3t'
    expect_grep "  ...owner/name parsed"         out 'owner/name from origin: acme/widget'
done

git -C "$repo" remote remove origin
printf '{"a": 1,}\n' > "$repo/.claude/settings.json"
expect_ok "no origin, broken settings.json"      env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
expect_grep "  ...GitHub not read"               out 'not read: no origin remote to name the repo'
expect_grep "  ...parse failure reported"        out 'parses: no:'

empty="$work/empty"
git init -q "$empty"
expect_ok "empty repo, no settings"              env PATH="$stub:$PATH" "$bash_bin" "$facts" "$empty"
expect_grep "  ...no commits"                    out 'commits on HEAD: 0'
expect_grep "  ...settings.json absent"          out 'present: no'
mkdir -p "$empty/.claude"
printf '{}\n' > "$empty/.claude/settings.json"
expect_ok "empty repo, new settings.json"        env PATH="$stub:$PATH" "$bash_bin" "$facts" "$empty"
expect_grep "  ...untracked"                     out 'tracked by git: no'
expect_grep "  ...HEAD unknown"                  out 'differs from HEAD: unknown (no commits)'

loose="$work/loose"
git init -q "$loose"
git -C "$loose" config user.email t@example.com
git -C "$loose" config user.name test
git -C "$loose" config commit.gpgsign false
printf 'x\n' > "$loose/README.md"
git -C "$loose" add README.md && git -C "$loose" commit -qm init
mkdir -p "$loose/.claude"
printf '{}\n' > "$loose/.claude/settings.json"
expect_ok "untracked settings.json"              env PATH="$stub:$PATH" "$bash_bin" "$facts" "$loose"
expect_grep "  ...untracked"                     out 'tracked by git: no'
expect_grep "  ...not in HEAD"                   out 'differs from HEAD: yes (not in HEAD)'
expect_grep "  ...no default branch"             out "origin default branch: unknown (no local origin/HEAD, and GitHub didn't say)"

linked="$work/linked"
git init -q "$linked"
git -C "$linked" config user.email t@example.com
git -C "$linked" config user.name test
git -C "$linked" config commit.gpgsign false
mkdir -p "$linked/.claude" "$linked/shared"
printf '{}\n' > "$linked/shared/settings.json"
ln -s ../shared/settings.json "$linked/.claude/settings.json"
git -C "$linked" add -A && git -C "$linked" commit -qm init
expect_ok "tracked symlinked settings.json"      env PATH="$stub:$PATH" "$bash_bin" "$facts" "$linked"
expect_grep "  ...symlink reported"              out 'symlink to: ../shared/settings.json'
expect_grep "  ...same as HEAD"                  out 'differs from HEAD: no'
ln -sf ../shared/other.json "$linked/.claude/settings.json"
cp "$linked/shared/settings.json" "$linked/shared/other.json"
expect_ok "symlink retargeted"                   env PATH="$stub:$PATH" "$bash_bin" "$facts" "$linked"
expect_grep "  ...differs from HEAD"             out 'differs from HEAD: yes'

if [ "$failures" -gt 0 ]; then
    printf 'test-repo-baseline: %d failed\n' "$failures" >&2
    exit 1
fi
printf 'test-repo-baseline: all passed\n'
