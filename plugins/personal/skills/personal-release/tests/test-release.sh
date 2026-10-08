#!/usr/bin/env bash
# Tests for templates/bump_version.py, templates/changelog.py, and
# scripts/release_facts.py against
# fixture repos. Needs only git and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
bump="$here/../templates/bump_version.py"
facts="$here/../scripts/release_facts.py"
changelog="$here/../templates/changelog.py"
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
    printf '{\n  "name": "@example/a",\n  "version": "2.4.0"\n}\n' > packages/a/package.json
    printf '{ "name": "dep", "version": "0.1.0" }\n' > node_modules/dep/package.json
    cat > pyproject.toml <<'EOF'
[tool.other]
version = "7"

[project]
name = "example"
version = "2.4.0"
EOF
    cat > Cargo.toml <<'EOF'
[package]
name = "example"
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

printf '{\n  "name": "@example/a",\n  "version": "2.4.9"\n}\n' > packages/a/package.json
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

printf '\nrelease lines\n'
fixture lines
expect_ok   "--line v2 allows a patch"               python3 "$bump" patch --line v2 --dry-run
expect_eq   "  ...2.4.1"                             "$(tail -1 "$work/out")" "2.4.1"
expect_ok   "--line v2 allows a minor"               python3 "$bump" minor --line v2 --dry-run
expect_eq   "  ...2.5.0"                             "$(tail -1 "$work/out")" "2.5.0"
expect_fail "--line v2 refuses a major"              python3 "$bump" major --line v2 --dry-run
expect_grep "  ...says it leaves the line"           "leaves the v2 line"
expect_ok   "--line v2.4 allows a patch"             python3 "$bump" patch --line v2.4 --dry-run
expect_fail "--line v2.4 refuses a minor"            python3 "$bump" minor --line v2.4 --dry-run
expect_fail "--line v3 refuses a 2.x version.txt"    python3 "$bump" patch --line v3 --dry-run
expect_grep "  ...says version.txt is off the line"  "isn't on the v3 line"
expect_fail "--line v2.5 refuses 2.4.0"              python3 "$bump" patch --line v2.5 --dry-run
expect_fail "--line needs vX or vX.Y"                python3 "$bump" patch --line 2.4 --dry-run
expect_fail "--line needs a value"                   python3 "$bump" patch --line
expect_eq   "dry runs changed nothing"               "$(git status --porcelain)" ""

# The Release workflow's own branch check, extracted from release.yml.
branch_check="$work/branch-check.sh"
python3 - "$here/../templates/release.yml" > "$branch_check" <<'EOF'
import sys
lines = open(sys.argv[1]).read().splitlines()
start = next(i for i, l in enumerate(lines) if l.strip() == "id: branch")
run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
indent = len(lines[run + 1]) - len(lines[run + 1].lstrip())
body = []
for l in lines[run + 1:]:
    if l.strip() and len(l) - len(l.lstrip()) < indent:
        break
    body.append(l[indent:])
print("\n".join(body))
EOF
for case in "main=" "release/v2=v2" "release/v2.4=v2.4" "release/v10.12=v10.12"; do
    ref=${case%%=*}
    want=${case#*=}
    : > "$work/gh-output"
    if GITHUB_REF_NAME="$ref" GITHUB_OUTPUT="$work/gh-output" bash "$branch_check" >/dev/null 2>&1; then
        expect_eq "workflow accepts $ref"            "$(sed -n 's/^line=//p' "$work/gh-output")" "$want"
    else
        fail "workflow refused $ref"
    fi
done
for ref in feature/x release/2.4 release/v2.4.1 release/vx release/v2.; do
    if GITHUB_REF_NAME="$ref" GITHUB_OUTPUT=/dev/null bash "$branch_check" >/dev/null 2>&1; then
        fail "workflow accepted $ref"
    else
        pass "workflow refuses $ref"
    fi
done

git switch -q -c release/v2
expect_ok   "facts on a major line"                  python3 "$facts"
expect_grep "  ...names it"                          "release line: v2 (major line: patches and minors)"
git switch -q -c release/v2.4
expect_ok   "facts on a minor line"                  python3 "$facts"
expect_grep "  ...names it"                          "release line: v2.4 (minor line: patches only)"

printf '\nrelease_facts.py\n'
fixture b
printf '{\n  "name": "@example/a",\n  "version": "2.4.1-rc.1"\n}\n' > packages/a/package.json
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

printf '\nchangelog.py\n'
fragment() {  # fragment <path> <kind> <body>
    mkdir -p "$(dirname "$1")"
    printf '```release-note:%s\n%s\n```\n' "$2" "$3" > "$1"
}
commit_at() {  # commit_at <epoch> <message>: fixed times make merge order testable
    GIT_AUTHOR_DATE="@$1 +0000" GIT_COMMITTER_DATE="@$1 +0000" git commit -qm "$2"
}
fixture frag
git branch -M main
mkdir .changelog && printf 'keeps the directory\n' > .changelog/README.md
cat > CHANGELOG.md <<'EOF'
# Changelog

## [Unreleased]

### Added

- Legacy entry from before fragments

## [v2.4.0] - 2026-01-01

- Earlier work
EOF
git add -A && commit_at 1700000000 "adopt fragments"
adopted=$(git rev-parse HEAD)
git switch -q -c one
fragment .changelog/zeta-feature.txt added 'Zeta feature, merged first'
git add -A && commit_at 1700000100 "add zeta"
git switch -q main && git switch -q -c two
fragment .changelog/alpha-fix.txt fixed $'Alpha fix with a long body\nthat wraps onto a second line'
printf '```release-note:added\nAlpha feature, merged second\n```\n' >> .changelog/alpha-fix.txt
git add -A && commit_at 1700000200 "add alpha"
git switch -q main
expect_ok   "branches with fragments merge cleanly"  git merge -q --no-edit one two
expect_ok   "check passes on valid fragments"        python3 "$changelog" check
expect_ok   "preview"                                python3 "$changelog" preview
expect_grep "  ...shows a fragment entry"            "- Zeta feature, merged first"

# The same two changes as CHANGELOG.md appends conflict: the problem fragments solve.
git switch -q -c append-one "$adopted" && printf -- '- One\n' >> CHANGELOG.md && git commit -qam one
git switch -q -c append-two "$adopted" && printf -- '- Two\n' >> CHANGELOG.md && git commit -qam two
expect_fail "  ...while two CHANGELOG.md appends conflict" git merge -q --no-edit append-one
git merge --abort 2>/dev/null
git switch -q main

expect_ok   "bump assembles the fragments"           python3 "$bump" patch --date 2026-10-08
expect_grep "  ...reports removed fragments"         "removed .changelog/alpha-fix.txt"
cat > "$work/want" <<'EOF'
# Changelog

## [v2.4.1] - 2026-10-08

### Added

- Legacy entry from before fragments
- Zeta feature, merged first
- Alpha feature, merged second

### Fixed

- Alpha fix with a long body
  that wraps onto a second line

## [v2.4.0] - 2026-01-01

- Earlier work
EOF
if diff -u "$work/want" CHANGELOG.md >"$work/out" 2>&1; then pass "  ...release section in merge order"; else fail "  ...release section"; sed 's/^/        /' "$work/out" >&2; fi
expect_eq   "  ...fragments deleted, README kept"    "$(ls -A .changelog)" "README.md"
git add -A && git commit -qm "release v2.4.1"
expect_ok   "an empty release still works"           python3 "$changelog" release 2.4.2 --date 2026-10-09 --dry-run
expect_grep "  ...and says it's empty"               "the release heading is empty"
expect_fail "refuses a version already released"     python3 "$changelog" release 2.4.1 --dry-run
expect_grep "  ...naming the heading"                "already has ## [v2.4.1]"

printf '\nchangelog.py check\n'
git switch -q -c pr-good
fragment .changelog/good.txt changed 'Something changed'
git add -A && git commit -qm good
expect_ok   "PR with a fragment passes --require"   python3 "$changelog" check --base main --require
expect_grep "  ...lists it"                          "fragment: .changelog/good.txt"
git switch -q main && git switch -q -c pr-none
printf 'code\n' > code.txt && git add -A && git commit -qm none
expect_fail "PR without a fragment fails --require" python3 "$changelog" check --base main --require
expect_grep "  ...points at the label"               "no-changelog"
expect_ok   "  ...passes without --require"          python3 "$changelog" check --base main
git switch -q main && git switch -q -c pr-edit
printf -- '- Sneaky\n' >> CHANGELOG.md && git commit -qam edit
expect_fail "PR editing CHANGELOG.md fails"          python3 "$changelog" check --base main
expect_grep "  ...says to add a fragment"            "CHANGELOG.md is edited directly"
git switch -q main
fragment .changelog/bad-kind.txt bugfix 'Wrong kind'
expect_fail "unknown kind fails"                     python3 "$changelog" check
expect_grep "  ...lists the kinds"                   "unknown kind 'bugfix'"
printf '```release-notes:fixed\nTypo in the fence\n```\n' > .changelog/bad-kind.txt
expect_fail "misspelled fence fails"                 python3 "$changelog" check
printf '```release-note:fixed\n\n```\n' > .changelog/bad-kind.txt
expect_fail "empty block fails"                      python3 "$changelog" check
expect_fail "release refuses bad fragments"          python3 "$changelog" release 2.4.2 --dry-run
rm .changelog/bad-kind.txt

printf '\nchangelog.py, several changelogs\n'
fixture multi
rm CHANGELOG.md
printf '# Changelog\n\n## [0.8.6] - 2026-10-01\n\n### Fixed\n\n- Old fix\n' > CHANGELOG.md
mkdir -p .changelog packages/a/.changelog
printf 'x\n' > .changelog/README.md && printf 'x\n' > packages/a/.changelog/README.md
printf '# Changelog\n\n## [Unreleased]\n\n## [0.3.0] - 2026-01-01\n\n- First\n' > packages/a/CHANGELOG.md
fragment .changelog/root.txt added 'Root entry'
fragment packages/a/.changelog/ext.txt fixed '- Already a bullet'
git add -A && git commit -qm multi
expect_ok   "release covers every CHANGELOG.md"     python3 "$changelog" release 0.8.7 --date 2026-10-10
expect_eq   "  ...keeps the file's no-v headings"   "$(grep -m1 '^## \[' CHANGELOG.md)" "## [0.8.7] - 2026-10-10"
expect_eq   "  ...inserts above the last release"   "$(sed -n '3,8p' CHANGELOG.md | tr '\n' '|')" "## [0.8.7] - 2026-10-10||### Added||- Root entry||"
expect_eq   "  ...nested changelog, bullet kept"    "$(sed -n '3,8p' packages/a/CHANGELOG.md | tr '\n' '|')" "## [0.8.7] - 2026-10-10||### Fixed||- Already a bullet||"
expect_eq   "  ...empty Unreleased heading dropped" "$(grep -c 'Unreleased' packages/a/CHANGELOG.md)" "0"
git add -A && git commit -qm "release" && fragment .changelog/next.txt security 'A fix'
git add -A && git commit -qm next
expect_ok   "facts report fragments"                 python3 "$facts"
expect_grep "  ...per directory"                     ".changelog/: 1 fragment file(s); release-note blocks: security 1"
expect_grep "  ...and the tooling"                   "  .changelog"

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf 'test-release: %d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'test-release: all passed\n'
