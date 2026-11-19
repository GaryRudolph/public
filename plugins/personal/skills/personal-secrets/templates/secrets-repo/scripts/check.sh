#!/usr/bin/env bash
# Keyless checks: safe in CI and in the pre-commit hook, needs no age key.
# usage: check.sh [--staged | --range <base>..<head>]
#
# Always:   access.map parses; identities are repo__context with a known
#           context; every mapped file has src/ and dist/ ciphertext; no
#           orphaned src/ or dist/ files; no plaintext tracked under
#           src/ dist/ keys/; break-glass is a source and publish recipient.
# --staged: also refuse a commit that stages plaintext under src/ dist/ keys/,
#           changes src/<f>.sops without dist/<f>.sops, or changes access.map
#           without any dist/ change (run make build first).
# --range:  the same pairing rules over a commit range, for the CI check.
#
# Fails closed: if find, git ls-files or git diff can't list the files a rule
# needs, the check fails and names the listing, rather than passing a scan it
# never made.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

mode=${1:-}
failures=0
fail() {
    printf 'FAIL: %s\n' "$*" >&2
    failures=$((failures + 1))
}

# Whether newline-separated list $1 holds line $2 exactly. A shell match,
# not printf | grep -q: under pipefail, grep -q exiting on a match can
# SIGPIPE a long printf and read as no match.
nl='
'
has_line() {
    case "$nl$1$nl" in *"$nl$2$nl"*) return 0 ;; esac
    return 1
}

# --- access.map -------------------------------------------------------------
if entries=$(access_entries); then
    while read -r file ids; do
        [ -n "$file" ] || continue
        case "$file" in */../*|../*|/*) fail "$file: paths must stay under src/" ;; esac
        for id in $ids; do
            ctx=${id##*__}
            case "$id" in
                *__*) is_context "$ctx" || fail "$file: $id has unknown context '$ctx' (use: $CONTEXTS)" ;;
                *)    fail "$file: '$id' isn't a repo__context identity or @group" ;;
            esac
        done
        [ -f "src/$file.sops" ] || fail "$file is in $ACCESS_MAP but src/$file.sops is missing"
        [ -f "dist/$file.sops" ] || fail "$file is in $ACCESS_MAP but dist/$file.sops is missing (make build)"
    done <<< "$entries"
else
    fail "$ACCESS_MAP doesn't parse"
    entries=""
fi

# A src/ or dist/ that doesn't exist holds no files; any other find failure
# fails the check (see the header).
list_sops() {
    [ -d "$1" ] || return 0
    find "$1" -type f -name '*.sops' | sort
}
src_files=$(list_sops src) || fail "cannot list src/: find failed"
dist_files=$(list_sops dist) || fail "cannot list dist/: find failed"

mapped_files=$(printf '%s\n' "$entries" | awk 'NF { print $1 }')
# Lists are read a line at a time, never word-split: an unquoted expansion
# would glob, so dist/[ab].env.sops could check dist/a.env.sops instead.
while IFS= read -r f; do
    [ -n "$f" ] || continue
    logical=${f#*/}
    has_line "$mapped_files" "${logical%.sops}" \
        || fail "$f is not listed in $ACCESS_MAP (map it, or delete it)"
done <<< "$src_files$nl$dist_files"

# --- tracked plaintext --------------------------------------------------------
tracked=$(git ls-files -- src dist keys) || fail "cannot list tracked files: git ls-files failed"
plain=$(printf '%s\n' "$tracked" | grep -v '\.sops$' | grep -v '/\.gitkeep$' || true)
[ -z "$plain" ] || fail "plaintext is tracked: $(printf '%s' "$plain" | tr '\n' ' ')"

# --- break-glass ------------------------------------------------------------
if [ -f "$BREAKGLASS" ]; then
    bg=$(breakglass_pub)
    grep -qF "$bg" .sops.yaml 2>/dev/null || fail "$BREAKGLASS isn't a source recipient in .sops.yaml"
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        grep -qF "$bg" "$f" || fail "$f isn't encrypted to break-glass (make build)"
    done <<< "$dist_files"
else
    fail "$BREAKGLASS is missing"
fi

# --- pairing: src change needs a dist change --------------------------------
check_pairing() {
    local changed="$1" f logical
    while IFS= read -r f; do
        case "$f" in
            src/*|dist/*|keys/*) ;;
            *) continue ;;
        esac
        case "$f" in
            *.sops|*/.gitkeep) ;;
            *) fail "$f is plaintext; only *.sops may be committed under src/ dist/ keys/" ;;
        esac
    done <<< "$changed"
    while IFS= read -r f; do
        case "$f" in src/*.sops) ;; *) continue ;; esac
        logical=${f#src/}
        has_line "$changed" "dist/$logical" \
            || fail "$f changed without dist/$logical (make build)"
    done <<< "$changed"
    if has_line "$changed" "$ACCESS_MAP"; then
        case "$nl$changed" in
            *"${nl}dist/"*) ;;
            *) fail "$ACCESS_MAP changed without any dist/ change (make build)" ;;
        esac
    fi
}

case "$mode" in
    "") ;;
    --staged)
        changed=$(git diff --cached --name-only --diff-filter=ACMRD) \
            || fail "cannot list staged changes: git diff --cached failed"
        check_pairing "$changed"
        ;;
    --range)
        [ -n "${2:-}" ] || die "usage: check.sh --range <base>..<head>"
        # A range CI can't resolve (a shallow clone, a force-pushed base) fails
        # here rather than pairing-checking nothing.
        changed=$(git diff --name-only --diff-filter=ACMRD "$2") \
            || fail "cannot list changes in $2: git diff failed"
        check_pairing "$changed"
        ;;
    *) die "usage: check.sh [--staged | --range <base>..<head>]" ;;
esac

if [ "$failures" -gt 0 ]; then
    printf '%d check(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'check: ok\n'
