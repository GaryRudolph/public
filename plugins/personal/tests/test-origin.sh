#!/usr/bin/env bash
# Tests for scripts/origin.py: the CLI's tab line and JSON, masking, and the
# Python interface against a real repo. Needs bash, git, and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
origin="$here/../scripts/origin.py"
python=$(command -v python3)
work=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
TAB=$(printf '\t')

# expect_line <name> <url> <host_class> <host> <owner> <repo> <transport> <masked>
expect_line() {
    local name="$1" url="$2" want got
    want=$(printf '%s\t%s\t%s\t%s\t%s\t%s' "$3" "$4" "$5" "$6" "$7" "$8")
    got=$("$python" -I "$origin" -- "$url" 2>&1)
    if [ "$got" = "$want" ]; then pass "$name"; else fail "$name: want '$want', got '$got'"; fi
}

printf 'host classes\n'
expect_line "https"                     "https://github.com/acme/widget.git"            github github.com acme widget https "https://github.com/acme/widget.git"
expect_line "https, no .git, slash"     "https://GitHub.com/acme/widget/"               github github.com acme widget https "https://GitHub.com/acme/widget/"
expect_line "scp form"                  "git@github.com:acme/widget.git"                github github.com acme widget ssh "git@github.com:acme/widget.git"
expect_line "proxy form"                "http://local_proxy@127.0.0.1:41923/git/acme/widget" proxy 127.0.0.1 acme widget http "http://***@127.0.0.1:41923/git/acme/widget"
expect_line "ssh alias, scp form"       "git@github.com-work:acme/widget.git"           alias github.com-work acme widget ssh "git@github.com-work:acme/widget.git"
expect_line "ssh alias, ssh url"        "ssh://git@github.com-work:22/acme/widget.git"  alias github.com-work acme widget ssh "ssh://git@github.com-work:22/acme/widget.git"
expect_line "ssh over 443"              "ssh://git@ssh.github.com:443/acme/widget.git"  ssh443 ssh.github.com acme widget ssh "ssh://git@ssh.github.com:443/acme/widget.git"
expect_line "gitlab"                    "https://gitlab.com/acme/widget.git"            other gitlab.com acme widget https "https://gitlab.com/acme/widget.git"
expect_line "attacker host, trusted owner" "https://attacker.example/lolay/x.git"       other attacker.example lolay x https "https://attacker.example/lolay/x.git"
expect_line "dotted alias is other"     "git@github.com-evil.example:lolay/x.git"       other github.com-evil.example lolay x ssh "git@github.com-evil.example:lolay/x.git"
expect_line "https alias is other"      "https://github.com-work/lolay/x.git"           other github.com-work lolay x https "https://github.com-work/lolay/x.git"
expect_line "github.com as a path is other" "https://evil.example/github.com/lolay/x"   other evil.example lolay x https "https://evil.example/github.com/lolay/x"
expect_line "proxy path must start /git/" "http://127.0.0.1:9/other/acme/widget"         other 127.0.0.1 acme widget http "http://127.0.0.1:9/other/acme/widget"
expect_line "proxy needs exactly owner/repo" "http://127.0.0.1/git/acme"           other 127.0.0.1 git acme http "http://127.0.0.1/git/acme"
expect_line "# ends the authority"      "https://evil.example#@github.com/GaryRudolph/x" other evil.example - - https "https://evil.example#@github.com/GaryRudolph/x"
expect_line "? ends the authority"      "https://evil.example?@github.com/GaryRudolph/x" other evil.example - - https "https://evil.example?***"
expect_line "ssh to an IP"              "ssh://git@10.0.0.5/acme/widget.git"            other 10.0.0.5 acme widget ssh "ssh://git@10.0.0.5/acme/widget.git"
expect_line "local path"                "/srv/git/widget.git"                           local - - - local "/srv/git/widget.git"
expect_line "file URL"                  "file:///srv/git/widget.git"                    local - - - file "file:///srv/git/widget.git"
expect_line "Windows path"              'C:\src\widget'                                 local - - - local 'C:\src\widget'
expect_line "empty"                     ""                                              none - - - - -

printf 'masking\n'
expect_line "https token as the user"   "https://ghp_SECRET@github.com/acme/widget.git" github github.com acme widget https "https://***@github.com/acme/widget.git"
expect_line "https user and password"   "https://bob:hunter2@github.com/acme/widget.git" github github.com acme widget https "https://***@github.com/acme/widget.git"
expect_line "ssh url with a password"   "ssh://bob:hunter2@host.example/acme/widget.git" other host.example acme widget ssh "ssh://bob:***@host.example/acme/widget.git"
expect_line "ssh url, user only"        "ssh://git@host.example/acme/widget.git"        other host.example acme widget ssh "ssh://git@host.example/acme/widget.git"
expect_line "git+ssh counts as ssh"     "git+ssh://bob:hunter2@host.example/a/b"        other host.example a b ssh "git+ssh://bob:***@host.example/a/b"
expect_line "a query string is masked"  "https://github.com/acme/widget.git?access_token=ghp_SECRET" github github.com acme widget https "https://github.com/acme/widget.git?***"
out=$("$python" -I "$origin" --json -- "https://ghp_SECRET@github.com/acme/widget.git" 2>&1); rc=$?
case "$out" in
    *ghp_SECRET*) fail "--json prints the token: $out" ;;
    *'"masked": "https://***@github.com/acme/widget.git"'*) [ "$rc" = 0 ] && pass "--json masks the token" || fail "--json exited $rc" ;;
    *) fail "--json: unexpected output: $out" ;;
esac

printf 'hostile input\n'
got=$("$python" -I "$origin" -- "$(printf 'https://github.com/lo\nlay/x')" 2>&1)
case "$got" in
    other"$TAB"-"$TAB"-"$TAB"-*) pass "a control character in the URL: other, no host or owner" ;;
    *) fail "control character: got '$got'" ;;
esac
[ "$(printf '%s\n' "$got" | wc -l | tr -d ' ')" = 1 ] && pass "  ...and the output is still one line" || fail "control character split the output"

printf 'interface\n'
if "$python" -I "$origin" >/dev/null 2>&1; then fail "no URL and no --repo: exit 0"; else
    [ "$("$python" -I "$origin" >/dev/null 2>&1; echo $?)" = 2 ] && pass "usage error exits 2" || fail "usage error: wrong exit"
fi
if "$python" -I "$origin" a b >/dev/null 2>&1; then fail "two URLs: exit 0"; else pass "two URLs is a usage error"; fi
json=$("$python" -I "$origin" --json -- "git@github.com-work:acme/widget.git")
if "$python" -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["host_class"]=="alias" and d["is_github"] is True and d["owner"]=="acme" and d["repo"]=="widget"' "$json"; then
    pass "--json: one object with is_github"
else
    fail "--json: $json"
fi
[ "$("$python" -c 'import json,sys; print(json.loads(sys.argv[1])["is_github"])' "$("$python" -I "$origin" --json -- "https://attacker.example/lolay/x.git")")" = False ] \
    && pass "an attacker host is not is_github" || fail "attacker host is_github"
[ "$("$python" -c 'import json,sys; print(json.loads(sys.argv[1])["is_github"])' "$("$python" -I "$origin" --json -- "https://github.com/lolay")")" = False ] \
    && pass "github.com with no repo is not is_github" || fail "github.com/lolay is_github"

printf 'read() from a repo\n'
r="$work/repo"; git init -q "$r"
got=$("$python" -I "$origin" --repo "$r"); [ "$got" = "none$TAB-$TAB-$TAB-$TAB-$TAB-" ] && pass "no origin: none" || fail "no origin: '$got'"
git -C "$r" remote add origin "https://tok@github.com/acme/widget.git"
got=$("$python" -I "$origin" --repo "$r"); want=$(printf 'github\tgithub.com\tacme\twidget\thttps\thttps://***@github.com/acme/widget.git')
[ "$got" = "$want" ] && pass "origin read, masked" || fail "origin: '$got'"
# read() asks `git remote get-url`, which applies insteadOf, as git itself would.
git -C "$r" config url."git@github.com-work:".insteadOf "gh:"
git -C "$r" remote set-url origin "gh:acme/widget.git"
got=$("$python" -I "$origin" --repo "$r" | cut -f1); [ "$got" = alias ] && pass "insteadOf shorthand is expanded" || fail "insteadOf: '$got'"
got=$("$python" -I "$origin" --repo "$work/not-a-repo"); [ "$got" = "none$TAB-$TAB-$TAB-$TAB-$TAB-" ] && pass "not a repo: none, no crash" || fail "not a repo: '$got'"

printf 'Python 3.9 floor\n'
if "$python" -c 'import ast,sys; ast.parse(open(sys.argv[1]).read(), feature_version=(3, 9))' "$origin"; then
    pass "origin.py parses as Python 3.9"
else
    fail "origin.py uses syntax newer than 3.9"
fi

if [ "$failures" -gt 0 ]; then
    printf '%d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'all origin tests passed\n'
