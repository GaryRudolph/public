#!/usr/bin/env bash
# Tests for scripts/review_log_facts.py against fixture repos: a repo with a
# log, registers and an accepted finding; a repo whose anchor was rewritten
# away; a workspace with repos.mk; a workspace whose members are cloned
# beside it, as on a runner; a plain folder matched by a glob; and members
# read from a previous estate register. Needs bash, git, python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
facts="$here/../scripts/review_log_facts.py"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
# PATH without gh, so --members never reaches GitHub from a test.
run()  { env PATH="$work/bin" python3 -I "$facts" --no-fetch "$@" >"$work/out" 2>"$work/err"; }
expect_ok()     { local d="$1"; shift; if run "$@"; then pass "$d"; else fail "$d (exit $?)"; sed 's/^/        /' "$work/err" >&2; fi; }
expect_rc()     { local d="$1" want="$2"; shift 2; run "$@"; local rc=$?; if [ "$rc" = "$want" ]; then pass "$d"; else fail "$d: exit $rc, expected $want"; fi; }
expect_grep()   { if grep -qF -- "$2" "$work/out"; then pass "$1"; else fail "$1: no '$2' in output"; sed 's/^/        /' "$work/out" >&2; fi; }
expect_nogrep() { if grep -qF -- "$2" "$work/out"; then fail "$1: '$2' in output"; else pass "$1"; fi; }

mkdir -p "$work/bin"
for tool in git python3 make; do
  p=$(command -v "$tool") && ln -s "$p" "$work/bin/$tool"
done

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

commit() { git add -A && git commit -qm "$1" && git rev-parse --short HEAD; }

# --- a reviewed repo ---------------------------------------------------------
repo="$work/estate/nowline-core"
mkdir -p "$repo" && cd "$repo" || exit 1
git init -q -b main
mkdir -p src tests
printf 'package core\nfunc A() {}\n' > src/a.go
printf 'package core\n' > tests/a_test.go
r1=$(commit base)
printf 'package core\nfunc A() {}\nfunc B() {}\n' > src/a.go
r2=$(commit "add B")
mkdir -p specs/reviews
cat > specs/reviews/2026-09-01-r1-full-findings.md <<EOF
# r1 full review: findings

- Kind: full
- Range: ..$r1

## correctness

### r1.f1 - Error swallowed in A

- Severity: high
- Kind: fix
- Location: \`src/a.go:2\` at $r1
- Status: fixed
- Resolution: #4

### r1.f2 - Vendored parser has no tests

- Severity: low
- Kind: decision
- Location: \`vendor/parse.go\` at $r1
- Status: accepted
- Reason: upstream owns it

### r1.f3 - B has no caller

- Severity: medium
- Kind: fix
- Location: \`src/a.go:3\` at $r2
- Status: open
EOF
cat > specs/reviews/README.md <<EOF
# Reviews

| Review | Date | Kind | Range | Findings | Issue | Outcome | Record |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | 2026-09-01 | full | ..$r1 | 1 high, 1 medium, 1 low | #3 | open | [summary](2026-09-01-r1-full.md) |
| r2 | 2026-10-01 | incremental | $r1..$r2 | none | | none | [summary](2026-10-01-r2-incremental.md) |
| r3 | 2026-10-15 | estate | $r1..$r2 | none here | #9 | open | [ws r1](x) |
EOF
commit "add reviews" >/dev/null
for i in 1 2 3; do printf 'func C%s() {}\n' "$i" >> src/a.go; commit "c$i" >/dev/null; done
head=$(git rev-parse HEAD)

echo "single repo with a log"
expect_ok "runs" "$repo"
expect_grep "layout" "layout: single_repo"
expect_grep "default branch" "default_branch: main (main, not fetched)"
expect_grep "head is the default branch" "head: $head"
expect_grep "log rows" "log: specs/reviews/README.md, 3 rows"
expect_grep "next review counts every kind" "next_review: r4"
expect_grep "anchor skips the estate row" "last_anchor: r2 incremental 2026-10-01 to=$(git rev-parse "$r2")"
expect_grep "anchor reachable" "reachable_from_default=yes"
expect_grep "last full" "last_full: r1 full"
expect_grep "last estate" "last_estate: r3 estate"
expect_grep "commits since anchor" "since_anchor: commits=4"
expect_grep "churn by bucket" "    source: 1 +3 -0"
expect_grep "churn by directory, for slicing" "    3 1 +3 -0 src/"
expect_grep "directory list header" "since_anchor_by_dir (changed_lines files +added -deleted dir, largest first):"
expect_grep "open finding" "r1.f3 | open | medium | fix"
expect_nogrep "fixed finding isn't open" "r1.f1 |"
expect_grep "accepted finding with reason" "r1.f2 | \`vendor/parse.go\` at $r1 | Vendored parser has no tests | upstream owns it"
expect_grep "hotspot" "src/a.go"
expect_nogrep "tests aren't hotspots" "tests/a_test.go"

echo "fix claims"
mkdir -p specs/reviews/r1 specs/reviews/r9
printf 'Finding: r1.f3\nClaim: fixed\nChange: B now called from A\nEvidence: TestA\n' > specs/reviews/r1/f3.md
printf 'Finding: r9.f1\nClaim: partial\n' > specs/reviews/r9/f1.md
printf 'notes\n' > specs/reviews/r1/notes.md
claim=$(commit "call B from A (#7)")
expect_ok "runs" "$repo"
expect_grep "claim count skips other files" "fix_claims (2):"
expect_grep "claim joined to its register status" "r1.f3 | r1.f3 | fixed | open | $claim call B from A (#7) | specs/reviews/r1/f3.md"
expect_grep "claim with no register" "r9.f1 | r9.f1 | partial | (not in a register) |"
expect_nogrep "claim dir isn't a register" "registers: 2"
git rm -rq specs/reviews/r1 specs/reviews/r9 && commit "read claims" >/dev/null
expect_ok "runs" "$repo"
expect_grep "deleted claims gone" "fix_claims (0):"
head=$(git rev-parse HEAD)

echo "reads the default branch, not the checked-out one"
git switch -qc feature "$r2"
printf 'func D() {}\n' >> src/a.go && commit d >/dev/null
expect_ok "runs on a branch cut before the log" "$repo"
expect_grep "head stays main" "head: $head"
expect_grep "checked out" "checked_out: feature"
expect_grep "records from main" "records_read_from: main"
expect_grep "log from main" "log: specs/reviews/README.md, 3 rows"
expect_grep "next review from main" "next_review: r4"
expect_grep "accepted finding from main" "r1.f2 |"
git switch -q main

echo "unmerged review branch takes its number"
git branch review/r4-incremental
expect_ok "runs" "$repo"
expect_grep "lists the branch" "unmerged_review_branches: review/r4-incremental"
expect_grep "skips its number" "next_review: r5"
git branch -q -D review/r4-incremental

echo "status values written loosely"
cat >> specs/reviews/2026-09-01-r1-full-findings.md <<'EOS'

### r1.f4 - Backticked status

- Severity: low
- Status: `accepted`
- Reason: fine as is

### r1.f5 - Unknown status

- Severity: low
- Status: wontfix
EOS
commit "loose statuses" >/dev/null
expect_ok "runs" "$repo"
expect_grep "backticks stripped" "r1.f4 |"
expect_grep "accepted count" "accepted_findings (2)"
expect_grep "unknown status surfaced" "r1.f5 | wontfix | Unknown status"

echo "anchor rewritten away"
other="$work/rewritten"
git clone -q "$repo" "$other" && cd "$other" || exit 1
git switch -q main
git reset -q --hard "$r1"
printf 'package core\nfunc Z() {}\n' > src/a.go
mkdir -p specs/reviews && cp "$repo/specs/reviews/README.md" specs/reviews/
commit "rewrite" >/dev/null
git update-ref -d refs/remotes/origin/HEAD 2>/dev/null; git update-ref -d refs/remotes/origin/main 2>/dev/null
git -C "$other" remote remove origin
expect_ok "runs" "$other"
expect_grep "anchor not on main" "reachable_from_default=no"
expect_nogrep "no churn from an unreachable anchor" "since_anchor:"

echo "shallow clone"
shallow="$work/shallow"
git clone -q --depth 2 "file://$repo" "$shallow"
expect_ok "runs" "$shallow"
expect_grep "reports shallow" "shallow: yes"
expect_grep "anchor outside history" "found=outside local history (shallow)"

echo "no log"
bare="$work/bare"
mkdir -p "$bare" && cd "$bare" && git init -q -b main && printf 'x\n' > a.py && commit a >/dev/null
expect_ok "runs" "$bare"
expect_grep "no log" "log: none"
expect_grep "first review" "next_review: r1"
expect_grep "no anchor" "last_anchor: none"

echo "estate members from a previous estate register"
cd "$repo" || exit 1
cat > specs/reviews/2026-10-15-r3-estate-findings.md <<'EOF'
# r3 estate review: findings

- Kind: estate
- Members: nowline-core a..b, nowline-cloud c..d
- Home: owner/nowline-core
EOF
commit "estate register" >/dev/null
expect_ok "runs" "$repo"
expect_grep "members recorded" "last_estate_members: nowline-core a..b, nowline-cloud c..d"

echo "plain folder of repos matched by a glob"
for name in nowline-cloud nowline-web other-tool; do
  mkdir -p "$work/estate/$name" && cd "$work/estate/$name" && git init -q -b main && printf 'x\n' > a.go && commit a >/dev/null
done
expect_ok "glob from the home repo" --members 'nowline*' "$repo"
expect_grep "local matches" "local ($work/estate): nowline-cloud, nowline-core, nowline-web"
expect_nogrep "non-matching repo" "other-tool"
expect_grep "no owner, no github lookup" "github: owner unknown (pass --owner)"
expect_grep "reports each member" "== repo nowline-web"
expect_ok "list from the folder" --members 'nowline-cloud,other-tool' "$work/estate"
expect_grep "plain folder layout" "layout: plain_folder"
expect_grep "list matches" "local ($work/estate): nowline-cloud, other-tool"
expect_nogrep "unlisted repo not reported" "== repo nowline-web"
expect_ok "plain folder without --members" "$work/estate"
expect_grep "lists candidates" "== repos in this folder (not members until confirmed): nowline-cloud, nowline-core, nowline-web, other-tool"

echo "github lookup that fails"
cat > "$work/bin/gh" <<'EOS'
#!/bin/sh
echo "HTTP 403: sessions are bound to their configured repositories" >&2
exit 1
EOS
chmod +x "$work/bin/gh"
expect_ok "runs" --members 'nowline*' --owner someone "$repo"
expect_grep "error shown, not none" "github: error: orgs/someone/repos: HTTP 403"
expect_grep "not-cloned unknown" "github_not_cloned: unknown"
cat > "$work/bin/gh" <<'EOS'
#!/bin/sh
case "$*" in
  *orgs/someone/repos*) printf 'someone/nowline-cloud\nsomeone/nowline-pro\nsomeone/other\n' ;;
  *) exit 1 ;;
esac
EOS
expect_ok "runs" --members 'nowline*' --owner someone "$repo"
expect_grep "org repos matched" "github: nowline-cloud, nowline-pro"
expect_grep "uncloned repo" "github_not_cloned: nowline-pro"
rm -f "$work/bin/gh"

echo "workspace with repos.mk"
ws="$work/ws"
mkdir -p "$ws" && cd "$ws" && git init -q -b main
printf 'REPOS := svc-a \\\n  svc-b\nREPOS += svc-c\n' > repos.mk
printf 'include repos.mk\nall:\n' > Makefile
commit ws >/dev/null
for name in svc-a svc-b; do
  mkdir -p "$ws/$name" && cd "$ws/$name" && git init -q -b main && printf 'x\n' > a.go && commit a >/dev/null
done
expect_ok "runs" "$ws"
expect_grep "workspace layout" "layout: workspace"
expect_grep "members from repos.mk" "== members from repos.mk: svc-a, svc-b, svc-c"
expect_grep "uncloned member" "svc-c: not cloned"
expect_grep "workspace reported" "== repo ws"
expect_grep "member reported" "== repo svc-b"

echo "estate findings delegated to members"
cd "$ws" || exit 1
printf 'svc-*/\n' > .gitignore
mkdir -p specs/reviews
printf '# r1 estate review: findings\n\n- Kind: estate\n- Members: svc-a a..b, svc-b c..d\n\n### r1.f1 - Client written twice\n\n- Severity: medium\n- Status: open\n- Contained: svc-a r1.f1, svc-b r2.f1, svc-c r1.f1\n\n### r1.f2 - Home-only decision\n\n- Severity: medium\n- Status: open\n' \
  > specs/reviews/2026-10-15-r1-estate-findings.md
commit "home estate register" >/dev/null
cd "$ws/svc-a" || exit 1
mkdir -p specs/reviews
printf '# r1 estate review: findings\n\n- Kind: estate\n- Home: ws r1\n\n### r1.f1 - Client written twice\n\n- Estate: ws r1.f1\n- Severity: medium\n- Status: fixed\n' \
  > specs/reviews/2026-10-15-r1-estate-findings.md
commit "member estate register" >/dev/null
expect_ok "runs" "$ws"
expect_grep "rollup header" "== estate rollup: home finding | home status | contained finding: status in its repo"
expect_grep "rollup row" "ws r1.f1 | open | svc-a r1.f1: fixed; svc-b r2.f1: (not in its registers); svc-c r1.f1: (repo not read)"
expect_nogrep "home-only finding not rolled up" "ws r1.f2 |"
expect_grep "delegated finding in the member" "r1.f1 | fixed | ws r1.f1"
expect_grep "home members still read" "last_estate_members: svc-a a..b, svc-b c..d"
expect_ok "member alone" "$ws/svc-a"
expect_nogrep "a member register isn't a members list" "last_estate_members"
expect_nogrep "no rollup without a home" "== estate rollup"
expect_ok "--members from the workspace root" --members 'svc*' "$ws"
expect_grep "members inside the workspace" "local ($ws): svc-a, svc-b"
expect_grep "nothing beside" "local_beside ($work): none"

echo "workspace whose members are siblings"
side="$work/side"
ws2="$side/side-workspace"
mkdir -p "$ws2" && cd "$ws2" && git init -q -b main
printf 'REPOS := side-a side-b side-c\n' > repos.mk
printf 'include repos.mk\nall:\n' > Makefile
commit ws2 >/dev/null
for dir in "$ws2/side-a" "$side/side-a" "$side/side-b"; do
  mkdir -p "$dir" && cd "$dir" && git init -q -b main && printf 'x\n' > a.go && commit a >/dev/null
done
expect_ok "runs" "$ws2"
expect_grep "inside wins over beside" "side-a: cloned inside ($ws2/side-a)"
expect_grep "member beside the workspace" "side-b: cloned beside ($side/side-b)"
expect_grep "member in neither place" "side-c: not cloned"
expect_grep "sibling member reported" "== repo side-b"
expect_ok "--members from the workspace root" --members 'side*' "$ws2"
expect_grep "matches inside" "local ($ws2): side-a"
expect_grep "matches beside" "local_beside ($side): side-b"
expect_nogrep "the workspace isn't beside itself" "side-b, side-workspace"
expect_nogrep "inside match not repeated beside" "local_beside ($side): side-a"
expect_grep "sibling reported" "== repo side-b"

echo "workspace whose parent can't be listed"
if [ "$(id -u)" = 0 ]; then
  echo "  skip  root reads any folder"
else
  shut="$work/shut"
  ws3="$shut/shut-workspace"
  mkdir -p "$ws3" && cd "$ws3" && git init -q -b main
  printf 'REPOS := shut-a\n' > repos.mk
  printf 'include repos.mk\nall:\n' > Makefile
  commit ws3 >/dev/null
  mkdir -p "$shut/shut-a" && cd "$shut/shut-a" && git init -q -b main && printf 'x\n' > a.go && commit a >/dev/null
  chmod u-r "$shut"
  expect_ok "runs with --members" --members 'shut*' "$ws3"
  expect_grep "unreadable, not none" "local_beside ($shut): unreadable"
  expect_ok "repos.mk still finds a member by name" "$ws3"
  expect_grep "member beside an unlistable parent" "shut-a: cloned beside ($shut/shut-a)"
  chmod u+r "$shut"
fi

echo "submodules are candidates"
sub="$work/sub"
mkdir -p "$sub" && cd "$sub" && git init -q -b main
printf '[submodule "vendor/lib"]\n\tpath = vendor/lib\n\turl = ../lib\n' > .gitmodules
commit sub >/dev/null
expect_ok "runs" "$sub"
expect_grep "candidates listed" "== submodules (candidates, not members until confirmed): vendor/lib"

echo "not a repo"
mkdir -p "$work/empty"
expect_rc "fails cleanly" 1 "$work/empty"

if [ "$failures" -gt 0 ]; then
  echo "codebase-review tests: $failures failed" >&2
  exit 1
fi
echo "all codebase-review tests passed"
