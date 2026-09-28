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
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

mode=${1:-}
failures=0
fail() {
    printf 'FAIL: %s\n' "$*" >&2
    failures=$((failures + 1))
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

mapped_files=$(printf '%s\n' "$entries" | awk 'NF { print $1 }')
orphans=$(for dir in src dist; do
    find "$dir" -type f -name '*.sops' 2>/dev/null | sort | while read -r f; do
        logical=${f#"$dir"/}
        printf '%s\n' "$mapped_files" | grep -qxF "${logical%.sops}" || printf '%s\n' "$f"
    done
done)
for f in $orphans; do
    fail "$f is not listed in $ACCESS_MAP (map it, or delete it)"
done

# --- tracked plaintext --------------------------------------------------------
if git rev-parse --git-dir >/dev/null 2>&1; then
    plain=$(git ls-files -- src dist keys | grep -v '\.sops$' | grep -v '/\.gitkeep$' || true)
    [ -z "$plain" ] || fail "plaintext is tracked: $(printf '%s ' $plain)"
fi

# --- break-glass ------------------------------------------------------------
if [ -f "$BREAKGLASS" ]; then
    bg=$(breakglass_pub)
    grep -qF "$bg" .sops.yaml 2>/dev/null || fail "$BREAKGLASS isn't a source recipient in .sops.yaml"
    for f in $(find dist -type f -name '*.sops' 2>/dev/null | sort); do
        grep -qF "$bg" "$f" || fail "$f isn't encrypted to break-glass (make build)"
    done
else
    fail "$BREAKGLASS is missing"
fi

# --- pairing: src change needs a dist change --------------------------------
check_pairing() {
    local changed="$1" f logical
    for f in $(printf '%s\n' "$changed" | grep -E '^(src|dist|keys)/' | grep -v '\.sops$' | grep -v '/\.gitkeep$' || true); do
        fail "$f is plaintext; only *.sops may be committed under src/ dist/ keys/"
    done
    for f in $(printf '%s\n' "$changed" | grep -E '^src/.*\.sops$' || true); do
        logical=${f#src/}
        printf '%s\n' "$changed" | grep -qxF "dist/$logical" \
            || fail "$f changed without dist/$logical (make build)"
    done
    if printf '%s\n' "$changed" | grep -qxF "$ACCESS_MAP" \
        && ! printf '%s\n' "$changed" | grep -q '^dist/'; then
        fail "$ACCESS_MAP changed without any dist/ change (make build)"
    fi
}

case "$mode" in
    "") ;;
    --staged) check_pairing "$(git diff --cached --name-only --diff-filter=ACMRD)" ;;
    --range)
        [ -n "${2:-}" ] || die "usage: check.sh --range <base>..<head>"
        check_pairing "$(git diff --name-only --diff-filter=ACMRD "$2")"
        ;;
    *) die "usage: check.sh [--staged | --range <base>..<head>]" ;;
esac

if [ "$failures" -gt 0 ]; then
    printf '%d check(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'check: ok\n'
