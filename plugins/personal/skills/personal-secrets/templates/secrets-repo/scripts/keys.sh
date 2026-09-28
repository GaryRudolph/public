#!/usr/bin/env bash
# Manage consumer keypairs in keys/repos.env.sops. Maintainer-local.
# usage: keys.sh mint|rotate|retire REPO CONTEXT
#
#   mint    generate a keypair for a new (repo, context); refuses if one exists
#   rotate  replace an existing keypair; refuses if none exists
#   retire  remove a keypair; refuses while access.map still grants it
#
# Private keys only ever pass through shell variables and the sops pipe; no
# plaintext registry touches disk. Nothing here talks to GitHub: follow up
# with `make build` and `CONFIRM_SET_KEYS=1 make set-keys`.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

op=${1:-}
id=$(identity_for "${2:-}" "${3:-}")
reg=$(registry_plain)
has_key=$([ -n "$(registry_field "$reg" "$id" public)" ] && echo yes || echo no)

without_id() {
    printf '%s\n' "$reg" | awk -v a="${id}__public=" -v b="${id}__private=" \
        'NF && index($0, a) != 1 && index($0, b) != 1'
}

new_pair() {
    local priv pub
    priv=$(age-keygen 2>/dev/null | grep '^AGE-SECRET-KEY-') || die "age-keygen failed"
    pub=$(printf '%s\n' "$priv" | age-keygen -y) || die "age-keygen -y failed"
    printf '%s__public=%s\n%s__private=%s\n' "$id" "$pub" "$id" "$priv"
}

granted() {
    access_entries | awk -v id="$id" '{ for (i = 2; i <= NF; i++) if ($i == id) { print $1; next } }'
}

case "$op" in
    mint)
        [ "$has_key" = no ] || die "$id already has a key; use: make rotate REPO=${id%__*} CONTEXT=${id##*__}"
        { without_id; new_pair; } | registry_write
        printf 'minted %s\n' "$id"
        ;;
    rotate)
        [ "$has_key" = yes ] || die "$id has no key to rotate; use: make mint REPO=${id%__*} CONTEXT=${id##*__}"
        { without_id; new_pair; } | registry_write
        printf 'rotated %s; the old key stops working once you run make build and push dist/\n' "$id"
        ;;
    retire)
        [ "$has_key" = yes ] || die "$id has no key"
        files=$(granted)
        [ -z "$files" ] || die "$id is still granted in $ACCESS_MAP: $(printf '%s ' $files)"
        without_id | registry_write
        printf 'retired %s\n' "$id"
        ;;
    *)
        die "usage: keys.sh mint|rotate|retire REPO CONTEXT"
        ;;
esac

if [ "$op" = retire ]; then
    printf 'next: commit, then delete the secret: gh secret delete SOPS_AGE_KEY -R <owner>/%s --app %s\n' "${id%__*}" "${id##*__}"
else
    printf 'next: grant it in %s if new, make build, commit, then CONFIRM_SET_KEYS=1 make set-keys REPO=%s CONTEXT=%s\n' \
        "$ACCESS_MAP" "${id%__*}" "${id##*__}"
fi
