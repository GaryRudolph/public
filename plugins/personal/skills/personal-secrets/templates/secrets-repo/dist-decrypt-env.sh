#!/usr/bin/env bash
# CONSUMER: dotenv secrets to stdout, never to disk.
# usage: [FILE=oss.env] [KEY=NAME] [FORMAT=dotenv] dist-decrypt-env.sh [root]
#
#   no KEY           KEY=VALUE lines for every env file this key can open
#                    (or just FILE)
#   KEY, no FORMAT   the raw value only, for one-command inline use
#   KEY + dotenv     one KEY=VALUE line, for >> "$GITHUB_ENV"
#
# env: SOPS_AGE_KEY (required). Files this key can't open are skipped with a
# note on stderr; that's expected, since each key opens only its own files.
# Self-contained: consumers check out only dist/ and the root files.
set -euo pipefail
root=${1:-dist}
sel_file=${FILE:-}
want_key=${KEY:-}
format=${FORMAT:-}

command -v sops >/dev/null 2>&1 || { echo "sops is not installed" >&2; exit 1; }
if [ -n "$want_key" ] && ! printf '%s' "$want_key" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$'; then
    echo "KEY must be an environment variable name" >&2
    exit 1
fi

emit_file() {
    local f=$1 logical=${1%.sops}
    logical=${logical#"$root"/}
    sops -d --input-type dotenv --output-type dotenv "$f" 2>/dev/null \
        || { echo "# skip $logical (this key can't decrypt it; expected)" >&2; return 1; }
}

value_of() {
    printf '%s\n' "$1" | awk -v k="$want_key" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }'
}

print_value() {
    if [ "$format" = dotenv ]; then
        printf '%s=%s\n' "$want_key" "$1"
    else
        printf '%s' "$1"
    fi
}

if [ -n "$want_key" ]; then
    if [ -n "$sel_file" ]; then
        f="$root/$sel_file.sops"
        [ -f "$f" ] || { echo "missing $f" >&2; exit 1; }
        content=$(emit_file "$f") || exit 1
        value=$(value_of "$content")
        [ -n "$value" ] || { echo "KEY $want_key not in $sel_file" >&2; exit 1; }
        print_value "$value"
        exit 0
    fi
    matches=""
    found=""
    while read -r f; do
        content=$(emit_file "$f" 2>/dev/null) || continue
        value=$(value_of "$content")
        [ -n "$value" ] || continue
        logical=${f%.sops}
        matches="$matches ${logical#"$root"/}"
        found=$value
    done < <(find "$root" -type f -name '*.env.sops' | sort)
    [ -n "$matches" ] || { echo "KEY $want_key not found in any env file this key can decrypt" >&2; exit 1; }
    if [ "$(printf '%s\n' $matches | wc -l | tr -d ' ')" -gt 1 ]; then
        echo "KEY $want_key is in more than one file:$matches" >&2
        echo "Pass FILE=<logical-name> to pick one." >&2
        exit 1
    fi
    print_value "$found"
    exit 0
fi

if [ -n "$sel_file" ]; then
    [ -f "$root/$sel_file.sops" ] || { echo "missing $root/$sel_file.sops" >&2; exit 1; }
    emit_file "$root/$sel_file.sops"
    exit 0
fi

find "$root" -type f -name '*.env.sops' | sort | while read -r f; do
    emit_file "$f" || true
done
