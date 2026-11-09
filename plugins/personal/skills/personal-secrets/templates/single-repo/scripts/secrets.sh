#!/usr/bin/env bash
# Single-repo secrets: SOPS + age files under secrets/<scope>/, per the
# personal secrets standard (standards/secrets/single-repo.md). Usually run
# through secrets.mk; run it from anywhere in the repo.
#
# usage: scripts/secrets.sh <command> [args]
#   encrypt [FILE]              cleartext -> FILE.sops, then delete the cleartext
#   decrypt [FILE]              FILE.sops -> cleartext, mode 0600 (CONFIRM=1 skips the .env prompt)
#   env FILE [KEY]              dotenv, or one value, to stdout (FORMAT=dotenv prints KEY=value)
#   check [--online]            keyless checks; --online also checks the repo is private
#   clean                       delete cleartext that has a .sops sibling, then check
#   updatekeys [SCOPE]          re-wrap a scope's files (ROTATE=1 also makes a new data key)
#   mint CONTEXT                new CI key: private half to GitHub, public half printed
#   sync ENVIRONMENT SERVICE    write <env>/<service>.env to Secret Manager; print --set-secrets bindings
#
# FILE is a path under secrets/ without .sops: prod/api.env, ci/AuthKey_X.p8.
# Written for bash 3.2 (macOS /bin/bash): no associative arrays, no mapfile.
# Never prints a secret value except where `env` is asked for one.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
SECRETS_DIR=${SECRETS_DIR:-secrets}
DEPLOY_DIR=${DEPLOY_DIR:-deploy}
dir="$root/$SECRETS_DIR"
umask 077

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*" >&2; }

[ -d "$dir" ] || die "$SECRETS_DIR/ not found under $root"
[ -f "$dir/.sops.yaml" ] || die "$SECRETS_DIR/.sops.yaml not found"
cd "$dir"

# sops on macOS looks in ~/Library/Application Support; people keep keys in
# ~/.config/sops/age/keys.txt, so point sops there when nothing else is set.
if [ -z "${SOPS_AGE_KEY:-}" ] && [ -z "${SOPS_AGE_KEY_FILE:-}" ]; then
    f="${XDG_CONFIG_HOME:-$HOME/.config}/sops/age/keys.txt"
    [ -f "$f" ] && export SOPS_AGE_KEY_FILE="$f"
fi

file_type() { case "$1" in *.env) printf 'dotenv' ;; *) printf 'binary' ;; esac; }

# "scope recipient name" for every key in every creation rule. Handles the
# kit's layout: `path_regex: ^<scope>/`, then age keys as `&name age1...`
# anchors, `*name` aliases, or plain age1 strings.
rules() {
    awk '
        { sub(/#.*/, "") }
        /path_regex:/ {
            scope = "?"
            if (match($0, /\^[a-z0-9][a-z0-9-]*\//)) scope = substr($0, RSTART + 1, RLENGTH - 2)
            next
        }
        /\*[A-Za-z0-9_-]+/ && !/age1/ {
            match($0, /\*[A-Za-z0-9_-]+/); n = substr($0, RSTART + 1, RLENGTH - 1)
            print scope, (n in key ? key[n] : "unknown-alias-" n), n
            next
        }
        /age1[0-9a-z]+/ {
            n = "-"
            if (match($0, /&[A-Za-z0-9_-]+/)) n = substr($0, RSTART + 1, RLENGTH - 1)
            line = $0
            while (match(line, /age1[0-9a-z]+/)) {
                k = substr(line, RSTART, RLENGTH)
                if (n != "-") key[n] = k
                print scope, k, n
                line = substr(line, RSTART + RLENGTH)
            }
        }
    ' .sops.yaml
}

scopes() { rules | awk '{print $1}' | sort -u; }
is_scope() { scopes | grep -qx "$1"; }
# A deploy environment is a scope with config in deploy/<scope>.env. Other
# non-ci scopes are GitHub environments for one privileged job (terraform-prod).
deploy_scopes() {
    local s
    for s in $(scopes); do [ "$s" != ci ] && [ -f "$root/$DEPLOY_DIR/$s.env" ] && echo "$s"; done
    return 0
}

file_recipients() {
    if [ "$(file_type "${1%.sops}")" = dotenv ]; then
        sed -n 's/^sops_age__list_[0-9]*__map_recipient=//p' "$1"
    else
        grep -o '"recipient": *"age1[0-9a-z]*"' "$1" | grep -o 'age1[0-9a-z]*'
    fi | sort -u
}

is_sops_output() { grep -qE '^sops_version=|"sops": *\{' "$1"; }

# Logical path (under secrets/, no .sops) from whatever the caller passed.
logical() {
    local f="${1#./}"
    f="${f#$SECRETS_DIR/}"
    printf '%s' "${f%.sops}"
}

# Every file under a scope folder, as logical paths: ciphertext or cleartext.
cipher_files() {
    local s
    for s in $(scopes); do
        if [ -d "$s" ]; then find "$s" -type f -name '*.sops' ! -name '*.tmp.*'; fi
    done | sort
}
clear_files() {
    local s
    for s in $(scopes); do
        if [ -d "$s" ]; then find "$s" -type f ! -name '*.sops' ! -name '*.tmp.*'; fi
    done | sort
}

decrypt_to_stdout() {
    local t
    t=$(file_type "${1%.sops}")
    sops -d --input-type "$t" --output-type "$t" "$1"
}

# --- commands --------------------------------------------------------------

cmd_encrypt() {
    local sel="${1:-}" f t tmp list
    if [ -n "$sel" ]; then list=$(logical "$sel"); else list=$(clear_files); fi
    [ -n "$list" ] || { note "no cleartext to encrypt"; return 0; }
    for f in $list; do
        [ -f "$f" ] || die "$SECRETS_DIR/$f doesn't exist"
        case "$f" in */*) ;; *) die "$f isn't in a scope folder (ci/, <env>/)" ;; esac
        is_scope "${f%%/*}" || die "$f: no creation rule for scope ${f%%/*}/ in .sops.yaml"
        is_sops_output "$f" && die "$f is already SOPS output; decrypt it instead of encrypting again"
        t=$(file_type "$f")
        tmp="$f.sops.tmp.$$"
        if sops -e --filename-override "$f.sops" --input-type "$t" --output-type "$t" "$f" > "$tmp"; then
            mv "$tmp" "$f.sops"
            rm -f "$f"
            note "encrypted $SECRETS_DIR/$f.sops"
        else
            rm -f "$tmp"
            die "cannot encrypt $f"
        fi
    done
}

cmd_decrypt() {
    local sel="${1:-}" f c tmp list has_env=no ans
    if [ -n "$sel" ]; then
        list=$(logical "$sel")
        [ -f "$list.sops" ] || die "$SECRETS_DIR/$list.sops doesn't exist"
    else
        list=$(cipher_files | sed 's/\.sops$//')
    fi
    [ -n "$list" ] || { note "nothing to decrypt"; return 0; }
    for f in $list; do case "$f" in *.env) has_env=yes ;; esac; done
    if [ "$has_env" = yes ] && [ "${CONFIRM:-}" != 1 ]; then
        [ -t 0 ] || die "decrypting a .env writes cleartext to disk; re-run with CONFIRM=1 (code should use secrets-env)"
        printf 'This writes cleartext secrets to disk. Code should use secrets-env instead.\nType "yes" to continue: ' >&2
        read -r ans || ans=""
        [ "$ans" = yes ] || die "aborted"
    fi
    for f in $list; do
        c="$f.sops"
        tmp="$f.tmp.$$"
        if ! decrypt_to_stdout "$c" > "$tmp" 2>/dev/null; then
            rm -f "$tmp"
            if [ -n "$sel" ]; then die "cannot decrypt $c with the keys available"; fi
            note "skip $SECRETS_DIR/$c (no key here opens it)"
            continue
        fi
        if [ -f "$f" ]; then
            if cmp -s "$tmp" "$f"; then
                rm -f "$tmp"; note "unchanged $SECRETS_DIR/$f"; continue
            fi
            rm -f "$tmp"
            die "$SECRETS_DIR/$f exists and differs from $c; encrypt it or delete it first"
        fi
        mv "$tmp" "$f"
        chmod 600 "$f"
        note "decrypted $SECRETS_DIR/$f"
    done
}

cmd_env() {
    local f k="${2:-}"
    [ -n "${1:-}" ] || die "FILE is required, e.g. FILE=prod/api.env"
    f=$(logical "$1")
    case "$f" in *.env) ;; *) die "$f isn't a .env file; use secrets-decrypt for binary files" ;; esac
    [ -f "$f.sops" ] || die "$SECRETS_DIR/$f.sops doesn't exist"
    if [ -z "$k" ]; then
        sops -d --input-type dotenv --output-type dotenv "$f.sops"
        return
    fi
    printf '%s' "$k" | grep -Eq '^[A-Z][A-Z0-9_]*$' || die "KEY '$k' isn't an UPPER_SNAKE name"
    v=$(sops -d --input-type dotenv --output-type dotenv --extract "[\"$k\"]" "$f.sops") \
        || die "cannot read $k from $f.sops"
    if [ "${FORMAT:-}" = dotenv ]; then printf '%s=%s\n' "$k" "$v"; else printf '%s\n' "$v"; fi
}

cmd_check() {
    local bad=0 s f k want have first files keys envs upper
    err() { printf '  FAIL  %s\n' "$*" >&2; bad=1; }

    if grep -Eq '^[[:space:]]*-?[[:space:]]*(encrypted_regex|unencrypted_regex|encrypted_suffix|unencrypted_suffix|encrypted_comment_regex|unencrypted_comment_regex|mac_only_encrypted):' .sops.yaml; then
        err ".sops.yaml leaves some values unencrypted (encrypted_regex, *_suffix or mac_only_encrypted); encrypt everything"
    fi
    grep -q '<[a-z-]*-age-public-key>' .sops.yaml && err ".sops.yaml still has placeholder keys"
    [ -n "$(scopes)" ] || err ".sops.yaml has no creation rule with path_regex ^<scope>/"
    rules | grep -q 'unknown-alias-' && err ".sops.yaml uses an alias with no anchor above it"
    for s in $(scopes); do
        rules | awk -v s="$s" '$1 == s && $3 == "breakglass"' | grep -q . || err "scope $s/: break-glass (&breakglass) isn't a recipient"
    done

    # Only ciphertext is tracked under a scope folder.
    if git -C "$root" rev-parse >/dev/null 2>&1; then
        while IFS= read -r f; do
            case "$f" in */*) case "$f" in *.sops) ;; *) err "tracked cleartext: $SECRETS_DIR/$f" ;; esac ;; esac
        done < <(git ls-files)
    fi

    for f in $(find . -mindepth 2 -type f -name '*.sops' ! -name '*.tmp.*' | sed 's|^\./||' | sort); do
        s=${f%%/*}
        if ! is_scope "$s"; then err "$f: $s/ has no creation rule"; continue; fi
        want=$(rules | awk -v s="$s" '$1 == s {print $2}' | sort -u)
        have=$(file_recipients "$f")
        [ "$want" = "$have" ] || err "$f: recipients differ from the $s/ rule (run secrets-updatekeys SCOPE=$s)"
        case "$f" in
            *.env.sops)
                printf '%s' "${f##*/}" | grep -Eq '^[a-z0-9][a-z0-9-]*\.env\.sops$' \
                    || err "$f: name it for its consumer, in lowercase kebab-case (api.env)"
                while IFS= read -r line; do
                    case "$line" in ''|'#'*|sops_*) continue ;; esac
                    k=${line%%=*}
                    printf '%s' "$k" | grep -Eq '^[A-Z][A-Z0-9_]*$' || err "$f: key '$k' isn't UPPER_SNAKE"
                    case "${line#*=}" in 'ENC['*) ;; *) err "$f: $k isn't encrypted" ;; esac
                    for e in $(deploy_scopes); do
                        upper=$(printf '%s' "$e" | tr 'a-z-' 'A-Z_')
                        case "_${k}_" in *"_${upper}_"*) err "$f: key '$k' names an environment; the folder says that" ;; esac
                    done
                done < "$f"
                ;;
        esac
    done

    # Every deploy environment folder has the same files with the same keys.
    envs=$(deploy_scopes)
    first=""
    for s in $envs; do
        [ -d "$s" ] || continue
        files=$(cd "$s" && find . -type f -name '*.env.sops' | sed 's|^\./||' | sort)
        keys=$(for f in $files; do printf '%s: ' "$f"; grep -v '^sops_' "$s/$f" | grep '=' | sed 's/=.*//' | sort | tr '\n' ' '; echo; done)
        if [ -z "$first" ]; then first="$s"; want_keys="$keys"; continue; fi
        [ "$keys" = "$want_keys" ] || err "$s/ and $first/ don't have the same files and keys"
    done

    if [ "${1:-}" = --online ]; then
        command -v gh >/dev/null 2>&1 || err "gh is needed for the online check"
        [ "$(cd "$root" && gh repo view --json isPrivate -q .isPrivate 2>/dev/null)" = true ] \
            || err "the repo isn't private (or gh can't tell); a public repo keeps no $SECRETS_DIR/ folder"
    fi

    left=$(clear_files | tr '\n' ' ')
    [ -n "$left" ] && note "  note  cleartext on disk (gitignored): $left"
    [ "$bad" = 0 ] || die "secrets check failed"
    note "secrets check ok"
}

cmd_clean() {
    local f left=""
    for f in $(clear_files); do
        if [ -f "$f.sops" ]; then rm -f "$f"; note "removed $SECRETS_DIR/$f"
        else left="$left $f"; fi
    done
    [ -z "$left" ] || die "not encrypted yet:$left (secrets-encrypt them, or delete them)"
    cmd_check
}

cmd_updatekeys() {
    local s="${1:-}" f t list
    if [ -n "$s" ]; then
        is_scope "$s" || die "no creation rule for scope $s/"
        list=$(cipher_files | grep "^$s/" || true)
    else
        list=$(cipher_files)
    fi
    for f in $list; do
        t=$(file_type "${f%.sops}")
        sops updatekeys -y --input-type "$t" "$f" >/dev/null 2>&1 || die "updatekeys failed on $f (needs a key that opens it)"
        if [ "${ROTATE:-}" = 1 ]; then
            sops rotate -i --input-type "$t" --output-type "$t" "$f" || die "rotate failed on $f"
        fi
        note "updated $SECRETS_DIR/$f${ROTATE:+ (new data key)}"
    done
}

cmd_mint() {
    local ctx="${1:-}" repo name flag key priv pub
    command -v gh >/dev/null 2>&1 || die "gh is required"
    repo=${REPO:-$(cd "$root" && gh repo view --json nameWithOwner -q .nameWithOwner)}
    [ -n "$repo" ] || die "can't tell the repo; set REPO=<org>/<repo>"
    case "$ctx" in
        actions|agents|codespaces|dependabot) flag="--app $ctx" ;;
        env-?*)
            name=${ctx#env-}
            printf '%s' "$name" | grep -Eq '^[A-Za-z0-9._-]+$' || die "environment name '$name' has characters GitHub doesn't allow"
            flag="--env $name"
            ;;
        *) die "CONTEXT must be actions, env-<env>, agents, codespaces or dependabot" ;;
    esac
    key=$(age-keygen 2>/dev/null)
    priv=$(printf '%s\n' "$key" | grep '^AGE-SECRET-KEY-')
    pub=$(printf '%s\n' "$key" | age-keygen -y)
    # shellcheck disable=SC2086
    printf '%s' "$priv" | gh secret set SOPS_AGE_KEY -R "$repo" $flag
    key=""; priv=""
    printf 'identity: %s__%s\npublic:   %s\n' "${repo##*/}" "$ctx" "$pub"
    printf 'next: add it to %s/.sops.yaml as &%s under its scope, then make secrets-updatekeys SCOPE=<scope>\n' \
        "$SECRETS_DIR" "$(printf '%s' "$ctx" | tr '-' '_')"
}

cmd_sync() {
    local env="${1:-}" svc="${2:-}" project f line k v other ov hits vals name ver out=""
    [ -n "$env" ] && [ -n "$svc" ] || die "usage: sync ENVIRONMENT SERVICE"
    deploy_scopes | grep -qx "$env" || die "$env/ isn't a deploy environment (needs a creation rule and $DEPLOY_DIR/$env.env)"
    project=${GOOGLE_CLOUD_PROJECT:-}
    [ -n "$project" ] || die "GOOGLE_CLOUD_PROJECT isn't set (load deploy/$env.env)"
    f="$env/$svc.env.sops"
    [ -f "$f" ] || die "$SECRETS_DIR/$f doesn't exist"
    command -v gcloud >/dev/null 2>&1 || die "gcloud is required"

    tmp=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/secrets-sync.XXXXXX")
    trap 'rm -rf "$tmp"' EXIT
    mkdir "$tmp/v"

    decrypt_to_stdout "$f" > "$tmp/mine" || die "cannot decrypt $f with this job's key"
    while IFS= read -r line; do
        case "$line" in ''|'#'*) continue ;; esac
        k=${line%%=*}; v=${line#*=}
        if [ "$v" = "@estate" ]; then
            vals=""; hits=0
            for other in "${ESTATE_DIST:-$root/_secrets/dist}/$env"/*.env.sops; do
                [ -f "$other" ] || continue
                ov=$(sops -d --input-type dotenv --output-type dotenv --extract "[\"$k\"]" "$other" 2>/dev/null) || continue
                if [ "$hits" -gt 0 ] && [ "$ov" != "$vals" ]; then die "$k: estate files disagree"; fi
                vals=$ov; hits=$((hits + 1))
            done
            [ "$hits" -gt 0 ] || die "$k is @estate, but no estate file this key opens has it"
            v=$vals
        fi
        printf '%s' "$v" > "$tmp/v/$k"
    done < "$tmp/mine"

    # A key shared with another service's file must hold the same value.
    for other in "$env"/*.env.sops; do
        [ "$other" = "$f" ] && continue
        decrypt_to_stdout "$other" > "$tmp/other" 2>/dev/null || die "cannot decrypt $other to compare shared keys"
        while IFS= read -r line; do
            case "$line" in ''|'#'*) continue ;; esac
            k=${line%%=*}; ov=${line#*=}
            [ -f "$tmp/v/$k" ] || continue
            [ "$ov" = "@estate" ] && continue
            [ "$ov" = "$(cat "$tmp/v/$k")" ] || die "$k differs between $f and $other; make the copies match"
        done < "$tmp/other"
    done

    for k in $(ls "$tmp/v" | sort); do
        gcloud secrets describe "$k" --project="$project" >/dev/null 2>&1 \
            || die "store secret $k doesn't exist in $project; create it in infrastructure code"
        v=$(cat "$tmp/v/$k")
        if [ "$(gcloud secrets versions access latest --secret="$k" --project="$project" 2>/dev/null || true)" = "$v" ]; then
            name=$(gcloud secrets versions describe latest --secret="$k" --project="$project" --format='value(name)')
            note "$k: unchanged (version ${name##*/})"
        else
            name=$(printf '%s' "$v" | gcloud secrets versions add "$k" --project="$project" --data-file=- --format='value(name)') \
                || die "cannot add a version to $k"
            note "$k: added version ${name##*/}"
        fi
        ver=${name##*/}
        out="${out:+$out,}$k=$k:$ver"
    done
    printf '%s\n' "$out"
}

cmd=${1:-}
[ $# -gt 0 ] && shift
case "$cmd" in
    encrypt)    cmd_encrypt "$@" ;;
    decrypt)    cmd_decrypt "$@" ;;
    env)        cmd_env "$@" ;;
    check)      cmd_check "$@" ;;
    clean)      cmd_clean ;;
    updatekeys) cmd_updatekeys "$@" ;;
    mint)       cmd_mint "$@" ;;
    sync)       cmd_sync "$@" ;;
    *) die "usage: secrets.sh encrypt|decrypt|env|check|clean|updatekeys|mint|sync (see the header)" ;;
esac
