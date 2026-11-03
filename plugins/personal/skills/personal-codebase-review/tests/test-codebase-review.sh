#!/usr/bin/env bash
# Tests for scripts/review_log_facts.py against fixture repos: a repo with a
# log, registers and an accepted finding; a repo whose anchor was rewritten
# away; a workspace with repos.mk; a plain folder matched by a glob; and
# members read from a previous estate register. Needs bash, git, python3.
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
expect_grep "open finding" "r1.f3 | open | medium | fix"
expect_nogrep "fixed finding isn't open" "r1.f1 |"
expect_grep "accepted finding with reason" "r1.f2 | \`vendor/parse.go\` at $r1 | Vendored parser has no tests | upstream owns it"
expect_grep "hotspot" "src/a.go"
expect_nogrep "tests aren't hotspots" "tests/a_test.go"

echo "reads the default branch, not the checked-out one"
git switch -qc feature
printf 'func D() {}\n' >> src/a.go && commit d >/dev/null
expect_ok "runs on a feature branch" "$repo"
expect_grep "head stays main" "head: $head"
expect_grep "checked out" "checked_out: feature"
git switch -q main

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
expect_grep "gh missing" "github: gh missing"
expect_grep "reports each member" "== repo nowline-web"
expect_ok "list from the folder" --members 'nowline-cloud,other-tool' "$work/estate"
expect_grep "plain folder layout" "layout: plain_folder"
expect_grep "list matches" "local ($work/estate): nowline-cloud, other-tool"
expect_nogrep "unlisted repo not reported" "== repo nowline-web"
expect_ok "plain folder without --members" "$work/estate"
expect_grep "lists candidates" "== repos in this folder (not members until confirmed): nowline-cloud, nowline-core, nowline-web, other-tool"

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

echo "not a repo"
mkdir -p "$work/empty"
expect_rc "fails cleanly" 1 "$work/empty"

if [ "$failures" -gt 0 ]; then
  echo "codebase-review tests: $failures failed" >&2
  exit 1
fi
echo "all codebase-review tests passed"
