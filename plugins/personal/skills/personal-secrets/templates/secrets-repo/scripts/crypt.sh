#!/usr/bin/env bash
# src/ <-> .sops siblings, for editing. Maintainer-local: needs a source key.
# usage: crypt.sh decrypt|encrypt [logical-path-under-src]
#
# decrypt never overwrites an existing plaintext sibling (edit it, or
# `make clean`). encrypt writes <file>.sops with the .sops.yaml source rule,
# then deletes the plaintext.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

op=${1:-}
sel=${2:-}
umask 077

decrypt_one() {
    local cipher="$1" plain="${1%.sops}" t
    if [ -e "$plain" ]; then
        printf 'skip %s (plaintext exists: edit it, or make clean)\n' "$plain"
        return
    fi
    t=$(file_type "$plain")
    sops -d --input-type "$t" --output-type "$t" "$cipher" > "$plain" \
        || { rm -f "$plain"; die "cannot decrypt $cipher"; }
    printf 'decrypted %s\n' "$plain"
}

encrypt_one() {
    local plain="$1" t tmp="$1.sops.tmp.$$"
    t=$(file_type "$plain")
    if sops -e --input-type "$t" --output-type "$t" "$plain" > "$tmp"; then
        mv "$tmp" "$plain.sops"
        rm -f "$plain"
        printf 'encrypted %s.sops\n' "$plain"
    else
        rm -f "$tmp"
        die "cannot encrypt $plain"
    fi
}

case "$op" in
    decrypt)
        if [ -n "$sel" ]; then
            [ -f "src/$sel.sops" ] || die "src/$sel.sops doesn't exist"
            decrypt_one "src/$sel.sops"
        else
            find src -type f -name '*.sops' | sort | while read -r c; do decrypt_one "$c"; done
        fi
        ;;
    encrypt)
        if [ -n "$sel" ]; then
            [ -f "src/$sel" ] || die "src/$sel doesn't exist"
            encrypt_one "src/$sel"
        else
            find src -type f ! -name '*.sops' ! -name '*.tmp.*' ! -name '.gitkeep' | sort \
                | while read -r p; do encrypt_one "$p"; done
        fi
        ;;
    *)
        die "usage: crypt.sh decrypt|encrypt [logical-path-under-src]"
        ;;
esac
