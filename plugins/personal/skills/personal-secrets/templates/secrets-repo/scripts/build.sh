#!/usr/bin/env bash
# Re-encrypt src/ into dist/ for each file's PUBLISH recipients (its mapped
# consumer keys plus break-glass). Maintainer-local: needs a source key.
#
# Publish recipients are computed here from access.map + keys/repos.env.sops
# and never written down. sops runs with --config /dev/null for dist/ so the
# committed .sops.yaml (source recipients only) can't override them.
# dist/ files no longer in access.map are deleted, so a revoked file stops
# being served at HEAD.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

reg=$(registry_plain)
bg=$(breakglass_pub)
entries=$(access_entries) || die "fix $ACCESS_MAP first"
mapped=""

while read -r file ids; do
    [ -n "$file" ] || continue
    src="src/$file.sops"
    dst="dist/$file.sops"
    [ -f "$src" ] || die "$ACCESS_MAP lists $file but $src doesn't exist (make src-encrypt FILE=$file)"

    rcpts=$bg
    count=0
    for id in $(printf '%s\n' $ids | sort -u); do
        pub=$(registry_field "$reg" "$id" public)
        [ -n "$pub" ] || die "no key for $id in $REGISTRY (make mint REPO=${id%__*} CONTEXT=${id##*__})"
        rcpts="$rcpts,$pub"
        count=$((count + 1))
    done

    t=$(file_type "$file")
    mkdir -p "$(dirname "$dst")"
    tmp="$dst.tmp.$$"
    if sops -d --input-type "$t" --output-type "$t" "$src" \
        | sops --config /dev/null -e --age "$rcpts" --input-type "$t" --output-type "$t" /dev/stdin > "$tmp"; then
        mv "$tmp" "$dst"
    else
        rm -f "$tmp"
        die "failed to build $dst"
    fi
    printf 'built %-40s %d consumer key(s) + break-glass\n' "$dst" "$count"
    mapped="$mapped
$dst"
done <<< "$entries"

# Drop published files that access.map no longer lists.
find dist -type f -name '*.sops' 2>/dev/null | sort | while read -r f; do
    if ! printf '%s\n' "$mapped" | grep -qxF "$f"; then
        rm -f "$f"
        printf 'removed %s (no longer in %s)\n' "$f" "$ACCESS_MAP"
    fi
done
