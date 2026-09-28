#!/usr/bin/env bash
# Push each consumer's private key to GitHub as SOPS_AGE_KEY in the store for
# its context. Maintainer-local, and remote-mutating: the Makefile guards it
# behind CONFIRM_SET_KEYS=1.
# usage: OWNER=<org> set-consumer-keys.sh [REPO] [CONTEXT]
#
# The key goes to gh on stdin, never on the command line, so it doesn't show
# up in process listings or shell history.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib.sh

owner=${OWNER:-}
want_repo=${1:-}
want_ctx=${2:-}
case "$owner" in
    ""|"<"*) die "set OWNER to the GitHub org or user that owns the consumer repos (Makefile OWNER)" ;;
esac
[ -z "$want_ctx" ] || is_context "$want_ctx" || die "CONTEXT '$want_ctx' is not one of: $CONTEXTS"

reg=$(registry_plain)
[ -n "$reg" ] || die "$REGISTRY is empty; make mint first"
sent=0

while IFS='=' read -r k v; do
    case "$k" in *__private) ;; *) continue ;; esac
    base=${k%__private}
    repo=${base%__*}
    ctx=${base##*__}
    [ -z "$want_repo" ] || [ "$repo" = "$want_repo" ] || continue
    [ -z "$want_ctx" ] || [ "$ctx" = "$want_ctx" ] || continue
    is_context "$ctx" || die "unknown context '$ctx' for $repo; set it by hand"
    printf '%s' "$v" | gh secret set SOPS_AGE_KEY -R "$owner/$repo" --app "$ctx"
    printf 'set SOPS_AGE_KEY  %s/%s  (%s)\n' "$owner" "$repo" "$ctx"
    sent=$((sent + 1))
done <<< "$reg"

[ "$sent" -gt 0 ] || die "no keys matched REPO='${want_repo}' CONTEXT='${want_ctx}'"
