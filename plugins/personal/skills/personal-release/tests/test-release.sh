#!/usr/bin/env bash
# Tests for templates/bump_version.py and scripts/release_facts.py against
# fixture repos. Needs only git and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
bump="$here/../templates/bump_version.py"
facts="$here/../scripts/release_facts.py"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
expect_ok()   { local d="$1"; shift; if "$@" >"$work/out" 2>&1; then pass "$d"; else fail "$d"; sed 's/^/        /' "$work/out" >&2; fi; }
expect_fail() { local d="$1"; shift; if "$@" >"$work/out" 2>&1; then fail "$d (should have failed)"; else pass "$d"; fi; }
expect_eq()   { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1: expected '$3', got '$2'"; fi; }
expect_grep() { if grep -qF -- "$2" "$work/out"; then pass "$1"; else fail "$1: no '$2' in output"; sed 's/^/        /' "$work/out" >&2; fi; }

fixture() {
    local repo="$work/$1"
    rm -rf "$repo"
    mkdir -p "$repo/packages/a" "$repo/node_modules/dep"
    cd "$repo" || exit 1
    git init -q && git config user.email t@example.com && git config user.name test
    # The runner's global config may force signing; fixtures need plain tags.
    git config commit.gpgsign false && git config tag.gpgsign false
    printf '2.4.0\n' > version.txt
    cat > package.json <<'EOF'
{
  "name": "root",
  "private": true,
  "config": { "version": "9.9.9" },
  "version": "2.4.0",
  "dependencies": { "left-pad": "1.3.0" }
}
EOF
    printf '{\n  "name": "@acme/a",\n  "version": "2.4.0"\n}\n' > packages/a/package.json
    printf '{ "name": "dep", "version": "0.1.0" }\n' > node_modules/dep/package.json
    cat > pyproject.toml <<'EOF'
[tool.other]
version = "7"

[project]
name = "acme"
version = "2.4.0"
EOF
    cat > Cargo.toml <<'EOF'
[package]
name = "acme"
version = "2.4.0"

[dependencies]
serde = { version = "1.0.200" }
EOF
    cat > CHANGELOG.md <<'EOF'
# Changelog

## [Unreleased]

- Add the thing
- Fix the other thing

## [v2.4.0] - 2026-01-01

- Earlier work
EOF
    git add -A && git add -f node_modules && git commit -qm init && git tag v2.4.0
    printf 'x\n' > work.txt && git add work.txt && git commit -qm "feat: more work"
}

printf 'bump_version.py\n'
fixture a
snapshot=$(git status --porcelain)
expect_ok   "dry run succeeds"                       python3 "$bump" patch --dry-run
expect_eq   "dry run changes nothing"                "$(git status --porcelain)" "$snapshot"
expect_ok   "patch"                                  python3 "$bump" patch --date 2026-09-27
expect_eq   "last line is the new version"           "$(tail -1 "$work/out")" "2.4.1"
expect_eq   "version.txt"                            "$(cat version.txt)" "2.4.1"
expect_eq   "root package.json top-level version"   "$(python3 -c 'import json;print(json.load(open("package.json"))["version"])')" "2.4.1"
expect_eq   "  ...nested config.version untouched"   "$(python3 -c 'import json;print(json.load(open("package.json"))["config"]["version"])')" "9.9.9"
expect_eq   "workspace package.json"                 "$(python3 -c 'import json;print(json.load(open("packages/a/package.json"))["version"])')" "2.4.1"
expect_eq   "node_modules untouched"                 "$(python3 -c 'import json;print(json.load(open("node_modules/dep/package.json"))["version"])')" "0.1.0"
expect_eq   "pyproject [project] version"            "$(grep -A3 '^\[project\]' pyproject.toml | sed -n 's/^version = "\(.*\)"/\1/p')" "2.4.1"
expect_eq   "  ...[tool.other] untouched"            "$(sed -n '2p' pyproject.toml)" 'version = "7"'
expect_eq   "Cargo [package] version"                "$(sed -n '3p' Cargo.toml)" 'version = "2.4.1"'
expect_eq   "  ...dependency version untouched"      "$(grep serde Cargo.toml)" 'serde = { version = "1.0.200" }'
expect_eq   "only version lines changed"             "$(git diff --numstat -- package.json packages pyproject.toml Cargo.toml version.txt | awk '{a+=$1; d+=$2} END {print a"/"d}')" "5/5"
expect_eq   "changelog: new heading under Unreleased" "$(sed -n '3,7p' CHANGELOG.md | tr '\n' '|')" "## [Unreleased]||## [v2.4.1] - 2026-09-27||- Add the thing|"
expect_eq   "  ...older release intact"              "$(grep -c '## \[v2.4.0\] - 2026-01-01' CHANGELOG.md)" "1"
expect_eq   "  ...and its entries"                   "$(grep -c '^- Earlier work' CHANGELOG.md)" "1"
expect_eq   "  ...blank line before the old heading" "$(grep -B1 '## \[v2.4.0\]' CHANGELOG.md | head -1)" ""
expect_eq   "  ...blank line after the new heading" "$(grep -A1 '## \[v2.4.1\]' CHANGELOG.md | tail -1)" ""
git commit -qam "release v2.4.1"

expect_ok   "minor"                                  python3 "$bump" minor --date 2026-09-28
expect_eq   "  ...2.5.0"                             "$(cat version.txt)" "2.5.0"
expect_grep "  ...notes the empty Unreleased"        "was empty"
git commit -qam "release v2.5.0"
expect_ok   "major"                                  python3 "$bump" major --date 2026-09-29
expect_eq   "  ...3.0.0"                             "$(cat version.txt)" "3.0.0"
git checkout -q -- .

printf '{\n  "name": "@acme/a",\n  "version": "2.4.9"\n}\n' > packages/a/package.json
snapshot=$(git status --porcelain; git diff)
expect_fail "refuses out-of-step fields"             python3 "$bump" patch
expect_grep "  ...names the file"                    "packages/a/package.json version is 2.4.9"
expect_eq   "  ...and changes nothing"               "$(git status --porcelain; git diff)" "$snapshot"
git checkout -q -- .
for bad in v2.5.0 2.5.0-rc.1 2.5; do
    printf '%s\n' "$bad" > version.txt
    expect_fail "refuses version.txt '$bad'"          python3 "$bump" patch
done
git checkout -q -- .
expect_fail "refuses an unknown level"               python3 "$bump" huge

printf '\nrelease_facts.py\n'
fixture b
printf '{\n  "name": "@acme/a",\n  "version": "2.4.1-rc.1"\n}\n' > packages/a/package.json
git commit -qam "bump a"
expect_ok   "facts run"                              python3 "$facts" --next minor
sha=$(git rev-parse --short=7 HEAD)
count=$(git rev-list --count HEAD)
expect_grep "last tag"                               "last v-tag reachable from HEAD: v2.4.0"
expect_grep "commits since the tag"                  "commits since v2.4.0: 2"
expect_grep "  ...listed"                            "feat: more work"
expect_grep "build-version string"                   "build-version for HEAD: 2.4.0+$sha ($count)"
expect_grep "flags a pre-release suffix"             "has a pre-release/dev suffix"
expect_grep "flags a field that differs"             "differs from version.txt (2.4.0)"
expect_grep "private package noted"                  "package.json: version = 2.4.0  [private]"
if grep -q 'node_modules' "$work/out"; then fail "node_modules showed up in facts"; else pass "tracked node_modules skipped"; fi
expect_grep "changelog entries counted"              "## [Unreleased]: 2 entries"
expect_grep "surfaces: npm"                          "npm package (packages/a/package.json)"
expect_grep "surfaces: python"                       "Python package"
expect_grep "--next"                                 "minor: 2.4.0 -> 2.5.0"
printf 'y\n' >> work.txt
expect_ok   "facts on a dirty tree"                  python3 "$facts"
expect_grep "  ...dirty build-version"               "2.4.0+$sha.dirty ($count)"
if grep -qiE 'recommend|should (bump|release)' "$work/out"; then fail "facts made a recommendation"; else pass "facts make no recommendation"; fi

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf 'test-release: %d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'test-release: all passed\n'
