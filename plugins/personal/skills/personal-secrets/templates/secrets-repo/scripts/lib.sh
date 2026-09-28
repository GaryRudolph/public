# shellcheck shell=bash
# Shared helpers for the maintainer scripts. Sourced, never run directly.
#
# Written for bash 3.2 (macOS /bin/bash): no associative arrays, no mapfile.
# Consumer entrypoints (dist-decrypt*.sh) don't use this file, because a
# consumer's sparse checkout of dist/ doesn't include scripts/.

ACCESS_MAP=${ACCESS_MAP:-access.map}
REGISTRY=${REGISTRY:-keys/repos.env.sops}
BREAKGLASS=${BREAKGLASS:-breakglass.pub}
CONTEXTS="actions agents codespaces dependabot"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

# dotenv for *.env topics, binary for everything else (certs, keys, profiles).
file_type() {
    case "$1" in
        *.env) printf 'dotenv' ;;
        *)     printf 'binary' ;;
    esac
}

is_context() {
    case " $CONTEXTS " in
        *" $1 "*) return 0 ;;
        *)        return 1 ;;
    esac
}

# Validate REPO and CONTEXT arguments and print the identity repo__context.
identity_for() {
    local repo="$1" ctx="$2"
    [ -n "$repo" ] || die "REPO is required"
    [ -n "$ctx" ] || die "CONTEXT is required (one of: $CONTEXTS)"
    printf '%s' "$repo" | grep -Eq '^[A-Za-z0-9._-]+$' || die "REPO '$repo' has characters GitHub repo names can't"
    case "$repo" in *__*) die "REPO '$repo' contains '__', the identity delimiter" ;; esac
    is_context "$ctx" || die "CONTEXT '$ctx' is not one of: $CONTEXTS"
    printf '%s__%s' "$repo" "$ctx"
}

# Print one line per access.map file entry: "<file> <identity> <identity> ...",
# with @groups expanded. Groups must be defined before the lines that use them.
access_entries() {
    [ -f "$ACCESS_MAP" ] || die "$ACCESS_MAP not found (run from the secrets repo root)"
    awk '
        function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
        /^[ \t]*(#|$)/ { next }
        /^[ \t]*@/ {
            eq = index($0, "=")
            if (!eq) { printf "%s:%d: group line needs \"@name = ids\"\n", FILENAME, NR > "/dev/stderr"; bad = 1; next }
            group[trim(substr($0, 1, eq - 1))] = trim(substr($0, eq + 1))
            next
        }
        {
            colon = index($0, ":")
            if (!colon) { printf "%s:%d: expected \"<file>: <groups/identities>\"\n", FILENAME, NR > "/dev/stderr"; bad = 1; next }
            file = trim(substr($0, 1, colon - 1))
            if (file in seen) { printf "%s:%d: %s is listed twice\n", FILENAME, NR, file > "/dev/stderr"; bad = 1; next }
            seen[file] = 1
            n = split(trim(substr($0, colon + 1)), toks, /[ \t]+/)
            out = file
            for (t = 1; t <= n; t++) {
                tok = toks[t]
                if (tok == "") continue
                if (tok ~ /^@/) {
                    if (!(tok in group)) { printf "%s:%d: unknown group %s (define groups above their use)\n", FILENAME, NR, tok > "/dev/stderr"; bad = 1; continue }
                    m = split(group[tok], ids, /[ \t]+/)
                    for (j = 1; j <= m; j++) if (ids[j] != "") out = out " " ids[j]
                } else {
                    out = out " " tok
                }
            }
            print out
        }
        END { exit bad }
    ' "$ACCESS_MAP"
}

# The source keys come from the maintainer: SOPS_AGE_KEY_FILE, SOPS_AGE_KEY,
# or sops' default keys.txt. We only check that sops can open the registry.
registry_plain() {
    [ -f "$REGISTRY" ] || return 0
    sops -d --input-type dotenv --output-type dotenv "$REGISTRY" \
        || die "cannot decrypt $REGISTRY; these targets need a maintainer (source) age key"
}

# Encrypt dotenv from stdin to $REGISTRY, using the .sops.yaml source rule.
# Writes to a temp file first so a failure never leaves a truncated registry.
registry_write() {
    local tmp="$REGISTRY.tmp.$$"
    mkdir -p "$(dirname "$REGISTRY")"
    if sops --filename-override "${REGISTRY%.sops}" -e --input-type dotenv --output-type dotenv /dev/stdin > "$tmp"; then
        mv "$tmp" "$REGISTRY"
    else
        rm -f "$tmp"
        die "failed to write $REGISTRY"
    fi
}

# Look up one field (public or private) for an identity in registry text.
registry_field() {
    local reg="$1" id="$2" field="$3"
    printf '%s\n' "$reg" | awk -v k="${id}__${field}" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }'
}

breakglass_pub() {
    [ -f "$BREAKGLASS" ] || die "$BREAKGLASS not found"
    tr -d ' \t\r\n' < "$BREAKGLASS"
}
