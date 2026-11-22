#!/usr/bin/env bash
# CONSUMER: dotenv secrets to stdout, never to disk.
# usage: [FILE=oss.env] [KEY=NAME] [FORMAT=dotenv] dist-decrypt-env.sh [root]
#
#   no KEY           KEY=VALUE lines for every env file this key can open
#                    (or just FILE)
#   KEY, no FORMAT   the raw value only, for one-command inline use
#   KEY + dotenv     one KEY=VALUE line
#
# Under GitHub Actions (GITHUB_ACTIONS=true) every value printed is first
# registered with ::add-mask:: on stderr. Start the step with `exec 2>&1` so
# masks and output share one pipe, since the runner reads the two streams
# separately. Capture stdout in a variable or hand it to a tool that doesn't
# echo it; never let it reach the step log directly. Decrypt in the step that
# needs the value; never append it to $GITHUB_ENV.
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

# Every env file under root, listed up front so a find that can't run stops
# here: a partial list could hide a second file holding KEY and return the
# wrong value, or emit a partial environment.
env_files() {
    find "$root" -type f -name '*.env.sops' | sort \
        || { echo "cannot list $root/'s env files: find failed" >&2; return 1; }
}

value_of() {
    printf '%s\n' "$1" | awk -v k="$want_key" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }'
}

# Under GitHub Actions, register every value with the runner's log masker
# before printing it. The mask goes to stderr: callers capture stdout
# ($(...)) or redirect it, so a mask there would never reach the runner and
# would end up inside the value. The runner reads workflow commands from the
# step's stderr as well as its stdout. Each value is masked as printed and,
# since dotenv escapes newlines as \n, also line by line as it reads once
# unescaped, and without surrounding quotes. The runner percent-decodes
# command data, so % and CR are encoded or the wrong string gets masked.
# usage: mask_values raw "$value"; mask_values dotenv "$dotenv_lines". The
# mode is always given, so a value can't be taken for it. Takes arguments,
# not stdin, so nothing writes into a pipe it may not read. A line split out
# of a multi-line value (trailing CR dropped) is masked only from 4
# characters, so a `{` or `}` line doesn't blank every brace in the log; the
# whole value is always masked, as printed and trimmed of whitespace. The
# masks start on a fresh line, since stderr may hold an unterminated line
# (a progress bar) that would swallow the command.
mask_values() {
    [ "${GITHUB_ACTIONS:-}" = true ] || return 0
    local dotenv=0
    case "$1" in raw) ;; dotenv) dotenv=1 ;; *) echo "mask_values: mode must be raw or dotenv" >&2; return 1 ;; esac
    printf '%s\n' "$2" | awk -v dotenv="$dotenv" '
        BEGIN { print "" }
        function esc(s) { gsub(/%/, "%25", s); gsub(/\r/, "%0D", s); return s }
        function emit(s) { if (s ~ /[^[:space:]]/ && !(s in seen)) { seen[s] = 1; print "::add-mask::" esc(s) } }
        function one(s,   n, i, p, q) {
            emit(s)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
            emit(s)
            q = substr(s, 1, 1)
            if (length(s) > 1 && (q == "\"" || q == "\047") && substr(s, length(s)) == q) { s = substr(s, 2, length(s) - 2); emit(s) }
            n = split(s, p, /\\n/)
            if (n > 1) for (i = 1; i <= n; i++) { sub(/\r$/, "", p[i]); if (length(p[i]) >= 4) emit(p[i]) }
        }
        dotenv && /^[[:space:]]*(#|$)/ { next }
        dotenv { if (index($0, "=") == 0) next; one(substr($0, index($0, "=") + 1)); next }
        { one($0) }
    ' >&2
}

print_value() {
    mask_values raw "$1"
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
    files=$(env_files) || exit 1
    matches=""
    found=""
    while read -r f; do
        [ -n "$f" ] || continue
        content=$(emit_file "$f" 2>/dev/null) || continue
        value=$(value_of "$content")
        [ -n "$value" ] || continue
        logical=${f%.sops}
        matches="$matches ${logical#"$root"/}"
        found=$value
    done <<< "$files"
    [ -n "$matches" ] || { echo "KEY $want_key not found in any env file this key can decrypt" >&2; exit 1; }
    if [ "$(printf '%s\n' $matches | wc -l | tr -d ' ')" -gt 1 ]; then
        echo "KEY $want_key is in more than one file:$matches" >&2
        echo "Pass FILE=<logical-name> to pick one." >&2
        exit 1
    fi
    print_value "$found"
    exit 0
fi

# A whole file: mask its values, then print it.
print_env() {
    [ -n "$1" ] || return 0
    mask_values dotenv "$1"
    printf '%s\n' "$1"
}

if [ -n "$sel_file" ]; then
    [ -f "$root/$sel_file.sops" ] || { echo "missing $root/$sel_file.sops" >&2; exit 1; }
    content=$(emit_file "$root/$sel_file.sops") || exit 1
    print_env "$content"
    exit 0
fi

files=$(env_files) || exit 1
while read -r f; do
    [ -n "$f" ] || continue
    content=$(emit_file "$f") || continue
    print_env "$content"
done <<< "$files"
