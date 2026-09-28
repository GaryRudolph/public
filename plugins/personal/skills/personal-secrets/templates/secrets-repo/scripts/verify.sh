#!/usr/bin/env bash
# Full verification with the consumer keys. Maintainer-local: needs a source
# key to open keys/repos.env.sops.
#
# On top of check.sh, proves for every file and every registered identity:
#   - identities granted in access.map can decrypt dist/<file>.sops
#   - identities NOT granted cannot (no over-sharing)
#   - what they decrypt matches src/<file>.sops (dist/ is fresh)
#   - every identity in access.map has a keypair, and each keypair matches
# Decryption runs with only the consumer key in scope: HOME and
# XDG_CONFIG_HOME point at an empty directory, so the maintainer's own
# keys.txt can't make a denied read succeed.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

bash scripts/check.sh

reg=$(registry_plain)
entries=$(access_entries)
iso=$(mktemp -d)
trap 'rm -rf "$iso"' EXIT
failures=0
fail() {
    printf 'FAIL: %s\n' "$*" >&2
    failures=$((failures + 1))
}

as_consumer() {
    local priv="$1"
    shift
    env -u SOPS_AGE_KEY_FILE -u SOPS_AGE_KEY_CMD HOME="$iso" XDG_CONFIG_HOME="$iso" \
        SOPS_AGE_KEY="$priv" sops "$@"
}

identities=$(printf '%s\n' "$reg" | sed -n 's/__public=.*$//p' | sort -u)

# Every keypair is internally consistent.
for id in $identities; do
    pub=$(registry_field "$reg" "$id" public)
    priv=$(registry_field "$reg" "$id" private)
    [ -n "$priv" ] || { fail "$id has a public key but no private key"; continue; }
    [ "$(printf '%s\n' "$priv" | age-keygen -y)" = "$pub" ] || fail "$id: private key doesn't match its public key"
done

while read -r file ids; do
    [ -n "$file" ] || continue
    t=$(file_type "$file")
    want=$(sops -d --input-type "$t" --output-type "$t" "src/$file.sops" | shasum -a 256) \
        || die "cannot decrypt src/$file.sops"
    for id in $ids; do
        printf '%s\n' "$identities" | grep -qxF "$id" || fail "$file grants $id, which has no keypair (make mint)"
    done
    for id in $identities; do
        priv=$(registry_field "$reg" "$id" private)
        granted=no
        case " $ids " in *" $id "*) granted=yes ;; esac
        out="$iso/out"
        if as_consumer "$priv" -d --input-type "$t" --output-type "$t" "dist/$file.sops" > "$out" 2>/dev/null; then
            if [ "$granted" = no ]; then
                fail "$id can decrypt dist/$file.sops but isn't granted it (make build)"
            elif [ "$(shasum -a 256 < "$out")" != "$want" ]; then
                fail "dist/$file.sops is stale for $id (make build)"
            fi
        elif [ "$granted" = yes ]; then
            fail "$id is granted $file but can't decrypt dist/$file.sops (make build)"
        fi
        rm -f "$out"
    done
    printf 'verified %s\n' "$file"
done <<< "$entries"

if [ "$failures" -gt 0 ]; then
    printf '%d verification(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'verify: ok\n'
