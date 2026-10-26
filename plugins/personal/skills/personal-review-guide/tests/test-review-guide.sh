#!/usr/bin/env bash
# Tests for scripts/review_facts.py against a fixture repo with a base and a
# head. Needs only bash, git, and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
facts="$here/../scripts/review_facts.py"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
run()  { python3 -I "$facts" "$@" >"$work/out" 2>"$work/err"; }
expect_ok()     { local d="$1"; shift; if run "$@"; then pass "$d"; else fail "$d (exit $?)"; sed 's/^/        /' "$work/err" >&2; fi; }
expect_rc()     { local d="$1" want="$2"; shift 2; run "$@"; local rc=$?; if [ "$rc" = "$want" ]; then pass "$d"; else fail "$d: exit $rc, expected $want"; fi; }
expect_grep()   { if grep -qF -- "$2" "$work/out"; then pass "$1"; else fail "$1: no '$2' in output"; sed 's/^/        /' "$work/out" >&2; fi; }
expect_nogrep() { if grep -qF -- "$2" "$work/out"; then fail "$1: '$2' in output"; else pass "$1"; fi; }

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
repo="$work/repo"
mkdir -p "$repo" && cd "$repo" || exit 1
git init -q -b main
mkdir -p api orders tests docs .github
printf 'syntax = "proto3";\nmessage Order { string id = 1; }\n' > api/orders.proto
printf 'package orders\nfunc Create() {}\n' > orders/service.go
printf 'def test_a():\n    assert 1\n\ndef test_b():\n    assert 2\n' > tests/test_orders.py
printf 'old name\n' > docs/old.md
printf 'secret handling\n' > orders/auth_token.go
git add -A && git commit -qm base

git switch -qc feature
printf 'syntax = "proto3";\nmessage Order { string id = 1; string status = 2; }\n' > api/orders.proto
mkdir -p migrations && printf 'ALTER TABLE orders ADD status text;\n' > migrations/002_status.sql
printf 'def test_a():\n    assert 1\n' > tests/test_orders.py
git mv docs/old.md docs/new.md
printf 'h1:abc\n' > go.sum
printf 'secret handling, rotated\n' > orders/auth_token.go
cat > AGENTS.md <<'EOF'
# Agents

## Review surfaces

### Rendered diagrams

- Counts: any change under `examples/`
- Tag: [check]
- Preview: required

## Visual changes

Show before and after renders.

## Other
EOF
printf '## Summary\n\n## Review guide\n' > .github/pull_request_template.md
mkdir -p specs/handoffs && printf 'plan\n' > specs/handoffs/plan-orders-otter.md
printf 'review\n' > specs/handoffs/plan-orders-otter-review.md
git add -A && git commit -qm 'add order status'

printf 'committed diff against main\n'
expect_ok "runs with --base main --committed"            --base main --committed
expect_grep "  ...names the base"                         "base_ref: main (--base)"
expect_grep "  ...lists the commit"                       "add order status"
expect_grep "  ...proto is api"                           "M +1 -1 api api/orders.proto"
expect_grep "  ...migration is schema"                    "A +1 -0 schema migrations/002_status.sql"
expect_grep "  ...go.sum is generated"                    "generated go.sum"
expect_grep "  ...rename keeps the old path"              "docs/new.md (from docs/old.md)"
expect_grep "  ...test lines removed"                     "M -3 tests/test_orders.py"
expect_grep "  ...sensitive path"                         "auth: orders/auth_token.go"
expect_grep "  ...review surfaces section, verbatim"      "### Rendered diagrams"
expect_grep "  ...surface field kept"                     "- Preview: required"
expect_nogrep "  ...stops at the next ## heading"         "Show before and after renders."
expect_grep "  ...other before/after heading"             "mentions before/after, renders or snapshots: ## Visual changes"
expect_nogrep "  ...not a heading inside the section"      "snapshots: ### Rendered diagrams"
expect_grep "  ...PR template with a review guide"        ".github/pull_request_template.md (has ## Review guide: yes)"
expect_grep "  ...review draft listed"                    "specs/handoffs/plan-orders-otter-review.md"
expect_grep "  ...totals by bucket"                       "schema: 1 +1 -0"

printf 'working tree\n'
printf 'package orders\nfunc Create() { retry() }\n' > orders/service.go
printf 'new\n' > orders/new.go
expect_ok "runs on the working tree by default"          --base main
expect_grep "  ...uncommitted change counts"              "source orders/service.go"
expect_grep "  ...untracked file listed apart"            "source orders/new.go"
expect_ok "--committed leaves it out"                    --base main --committed
expect_nogrep "  ...no uncommitted file"                  "orders/service.go"
git checkout -q -- orders/service.go && rm orders/new.go

printf 'base discovery\n'
expect_ok "no remote: falls back to main"                --committed
expect_grep "  ...says how it found it"                   "base_ref: main (first that exists"
git switch -q main && git clone -q "$repo" "$work/clone" && git switch -q feature && git -C "$work/clone" switch -qc topic
expect_ok "clone: uses origin/HEAD"                      --committed "$work/clone"
expect_grep "  ...origin/main"                            "base_ref: origin/main (origin/HEAD)"

printf 'edges\n'
mkdir -p "$work/plain"
expect_rc "not a git repo: exit 1"                       1 "$work/plain"
git init -q -b trunk "$work/lonely" && git -C "$work/lonely" commit -q --allow-empty -m one
expect_ok "no base found: still prints"                  "$work/lonely"
expect_grep "  ...says none"                              "base_ref: none (none found)"
expect_grep "  ...no surfaces"                            "none"

if [ "$failures" -gt 0 ]; then
    printf '%s review-guide test(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'all review-guide tests passed\n'
