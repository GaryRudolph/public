#!/usr/bin/env bash
# CONSUMER: decrypt dist/ files to plaintext siblings on disk (owner-only
# permissions). Never emits environment assignments; use dist-decrypt-env.sh
# for dotenv secrets.
# usage: [FILE=ios/AuthKey_ABC123.p8] dist-decrypt.sh [root]
#
# env: SOPS_AGE_KEY (required). With FILE, failing to decrypt is an error;
# without it, files this key can't open are skipped with a note on stderr.
# Self-contained: consumers check out only dist/ and the root files.
set -euo pipefail
root=${1:-dist}
sel=${FILE:-}
umask 077

command -v sops >/dev/null 2>&1 || { echo "sops is not installed" >&2; exit 1; }

decrypt_one() {
    local f=$1 required=${2:-0} out=${1%.sops} rel t
    rel=${out#"$root"/}
    if [ ! -f "$f" ]; then
        echo "missing $f" >&2
        [ "$required" = 0 ] && return 0 || return 1
    fi
    case "$out" in
        *.env) t=dotenv ;;
        *)     t=binary ;;
    esac
    if sops -d --input-type "$t" --output-type "$t" "$f" > "$out" 2>/dev/null; then
        echo "decrypted $rel" >&2
    else
        rm -f "$out"
        echo "# skip $rel (this key can't decrypt it; expected)" >&2
        [ "$required" = 0 ] && return 0 || return 1
    fi
}

if [ -n "$sel" ]; then
    decrypt_one "$root/$sel.sops" 1
    exit 0
fi

find "$root" -type f -name '*.sops' | sort | while read -r f; do
    decrypt_one "$f"
done
