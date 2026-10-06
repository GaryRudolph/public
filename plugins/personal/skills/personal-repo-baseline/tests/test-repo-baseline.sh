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
        echo '{"allow_merge_commit":true,"allow_squash_merge":true,"full_name":"acme/widget","permissions":{"admin":false}}'
        ;;
esac
EOF
chmod +x "$stub/gh"
export GH_ARGS_FILE="$work/gh-args"

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
expect_grep "  ...settings.json tracked"         out 'tracked by git: yes'
expect_grep "  ...settings.json contents"        out '    |   "permissions": {"allow": []}'
expect_grep "  ...local attribution value"       out 'attribution: {"commit": ""}'
expect_grep "  ...local file ignored by git"     out 'ignored by git: yes'
expect_nogrep "  ...local values otherwise hidden" out 's3cr3t-value'
expect_grep "  ...GitHub values printed"         out '"allow_merge_commit": true'
expect_grep "  ...request names the repo"        gh-args 'repos/acme/widget'
for key in $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))))' "$gh_tmpl"); do
    expect_grep "  ...filter reads $key"         gh-args "$key"
done
expect_eq "  ...read-only"                       "$(git -C "$repo" status --porcelain)" "$snap"

expect_ok "gh refused"                           env PATH="$stub:$PATH" GH_STUB_FAIL=1 "$bash_bin" "$facts" "$repo"
expect_grep "  ...error reported"                out 'failed (exit 1): gh: Must have admin rights to Repository. (HTTP 403)'

nogh="$work/nogh"
mkdir -p "$nogh"
for t in git python3 sed head tr mktemp rm dirname; do ln -s "$(command -v "$t")" "$nogh/$t"; done
expect_ok "gh missing"                           env PATH="$nogh" "$bash_bin" "$facts" "$repo"
expect_grep "  ...says so"                       out 'gh: missing'

for url in git@github.com:acme/widget.git ssh://git@github.com/acme/widget http://local_proxy@127.0.0.1:1234/git/acme/widget; do
    git -C "$repo" remote set-url origin "$url"
    expect_ok "origin $url"                      env PATH="$stub:$PATH" "$bash_bin" "$facts" "$repo"
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

if [ "$failures" -gt 0 ]; then
    printf 'test-repo-baseline: %d failed\n' "$failures" >&2
    exit 1
fi
printf 'test-repo-baseline: all passed\n'
