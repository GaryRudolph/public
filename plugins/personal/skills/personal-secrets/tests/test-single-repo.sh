#!/usr/bin/env bash
# End-to-end test of templates/single-repo in a sandbox repo. Needs sops,
# age, age-keygen, git and make; skips cleanly without them. Stubs gh and
# gcloud, so nothing reaches GitHub or Google Cloud. Runs the script under
# bash 3.2 when /bin/bash is 3.2 (macOS).
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
kit="$here/../templates/single-repo"

for t in sops age age-keygen git make; do
    if ! command -v "$t" >/dev/null 2>&1; then
        printf 'SKIP: %s not installed (brew install sops age)\n' "$t"
        exit 0
    fi
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
expect_ok()   { local d="$1"; shift; if "$@" >"$work/out" 2>&1; then pass "$d"; else fail "$d"; sed 's/^/        /' "$work/out" >&2; fi; }
expect_fail() { local d="$1"; shift; if "$@" >"$work/out" 2>&1; then fail "$d (should have failed)"; sed 's/^/        /' "$work/out" >&2; else pass "$d"; fi; }
expect_eq()   { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1: expected '$3', got '$2'"; fi; }
expect_grep() { if grep -q -- "$2" "$work/out"; then pass "$1"; else fail "$1: no '$2' in output"; sed 's/^/        /' "$work/out" >&2; fi; }

# --- sandbox: bash 3.2 first on PATH, stub gh and gcloud --------------------
mkdir -p "$work/bin" "$work/keys" "$work/home" "$work/store"
[ -x /bin/bash ] && ln -s /bin/bash "$work/bin/bash"
cat > "$work/bin/gh" <<'EOF'
#!/bin/sh
printf 'ARGS %s\n' "$*" >> "$GH_LOG"
case "$1 $2" in
    "secret set") printf 'STDIN %s\n' "$(cat)" >> "$GH_LOG" ;;
    "repo view")
        case "$*" in
            *isPrivate*) echo "${GH_PRIVATE:-true}" ;;
            *) echo "o/app" ;;
        esac ;;
esac
EOF
# gcloud stub: $GCLOUD_STORE/<project>/<secret>/<version> holds each value.
cat > "$work/bin/gcloud" <<'EOF'
#!/bin/sh
proj=""; secret=""
for a in "$@"; do
    case "$a" in --project=*) proj=${a#--project=} ;; --secret=*) secret=${a#--secret=} ;; esac
done
latest() { ls "$1" 2>/dev/null | sort -n | tail -1; }
case "$1 $2" in
    "secrets describe") [ -d "$GCLOUD_STORE/$proj/$3" ] || exit 1 ;;
    "secrets versions")
        case "$3" in
            access)   d="$GCLOUD_STORE/$proj/$secret"; n=$(latest "$d"); [ -n "$n" ] || exit 1; cat "$d/$n" ;;
            describe) d="$GCLOUD_STORE/$proj/$secret"; n=$(latest "$d"); [ -n "$n" ] || exit 1; echo "projects/$proj/secrets/$secret/versions/$n" ;;
            add)      d="$GCLOUD_STORE/$proj/$4"; [ -d "$d" ] || exit 1; n=$(( $(ls "$d" | wc -l) + 1 )); cat > "$d/$n"; echo "projects/$proj/secrets/$4/versions/$n" ;;
        esac ;;
    *) exit 2 ;;
esac
EOF
chmod +x "$work/bin/gh" "$work/bin/gcloud"
export PATH="$work/bin:$PATH" GH_LOG="$work/gh.log" GCLOUD_STORE="$work/store" HOME="$work/home" XDG_CONFIG_HOME="$work/home"
# A parent make (make -C agents test) exports -w through MAKEFLAGS, which
# would print "Entering directory" into captured output.
unset MAKEFLAGS MAKELEVEL MFLAGS
unset SOPS_AGE_KEY SOPS_AGE_KEY_CMD SOPS_AGE_KEY_FILE GOOGLE_CLOUD_PROJECT
printf 'bash under test: %s\n' "$(bash -c 'echo $BASH_VERSION')"

for n in maint bg actions envdev envprod tfprod; do age-keygen -o "$work/keys/$n.txt" 2>/dev/null; done
pub() { age-keygen -y "$work/keys/$1.txt"; }
priv() { grep '^AGE-SECRET-KEY-' "$work/keys/$1.txt"; }
as() { local who="$1"; shift; env -u SOPS_AGE_KEY_FILE SOPS_AGE_KEY="$(priv "$who")" "$@"; }

repo="$work/app"
mkdir -p "$repo/scripts" "$repo/deploy" "$repo/secrets/ci" "$repo/secrets/dev" "$repo/secrets/prod" "$repo/secrets/terraform-prod"
cp "$kit/scripts/secrets.sh" "$repo/scripts/"
cp "$kit/secrets.mk" "$kit/secrets/README.md" "$repo/"
mv "$repo/README.md" "$repo/secrets/README.md"
cp "$kit/secrets.gitignore" "$repo/.gitignore"
printf 'SHELL := bash\ninclude secrets.mk\n' > "$repo/Makefile"
printf 'GOOGLE_CLOUD_PROJECT=demo-dev\n' > "$repo/deploy/dev.env"
printf 'GOOGLE_CLOUD_PROJECT=demo-prod\n' > "$repo/deploy/prod.env"
sed -e "s/<maintainer-age-public-key>/$(pub maint)/" -e "s/<breakglass-age-public-key>/$(pub bg)/" \
    -e "s/<actions-age-public-key>/$(pub actions)/" -e "s/<env-dev-age-public-key>/$(pub envdev)/" \
    -e "s/<env-prod-age-public-key>/$(pub envprod)/" "$kit/secrets/.sops.yaml" > "$repo/secrets/.sops.yaml"
cat >> "$repo/secrets/.sops.yaml" <<EOF
  - path_regex: ^terraform-prod/.+\.sops\$
    key_groups:
      - age:
          - *maintainer
          - *breakglass
          - &env_terraform_prod $(pub tfprod)
EOF
cd "$repo" || exit 1
git init -q && git config user.email t@example.com && git config user.name test
export SOPS_AGE_KEY_FILE="$work/keys/maint.txt"

printf 'APPLE_DISTRIBUTION_P12_PASSWORD=p12pass\n' > secrets/ci/deskhound.env
printf 'CLOUDFLARE_API_TOKEN=cf_read\n' > secrets/ci/terraform-plan.env
head -c 512 /dev/urandom > secrets/ci/apple-distribution.p12
cp secrets/ci/apple-distribution.p12 "$work/p12.orig"
printf 'CLOUDFLARE_API_TOKEN=cf_write\n' > secrets/terraform-prod/terraform.env
for e in dev prod; do
    printf 'RESEND_API_KEY=re_%s\n' "$e" > "secrets/$e/shared.env"
    printf 'DATABASE_PASSWORD=db_%s\n' "$e" > "secrets/$e/api.env"
    printf 'MCP_SIGNING_SECRET=mcp_%s\n' "$e" > "secrets/$e/mcp.env"
done

printf '\nencrypt\n'
expect_ok   "secrets-encrypt seals every cleartext file"        make secrets-encrypt
expect_eq   "cleartext is gone"                                  "$(find secrets -mindepth 2 -type f ! -name '*.sops' | wc -l | tr -d ' ')" "0"
expect_eq   "binary file sealed beside its name"                 "$(ls secrets/ci/apple-distribution.p12.sops)" "secrets/ci/apple-distribution.p12.sops"
cp secrets/prod/api.env.sops secrets/prod/api.env
expect_fail "encrypt refuses SOPS output"                        make secrets-encrypt FILE=prod/api.env
rm secrets/prod/api.env
printf 'X_TOKEN=1\n' > secrets/stray.env
expect_fail "encrypt refuses a file outside a scope"             make secrets-encrypt FILE=stray.env
rm secrets/stray.env
expect_ok   "secrets-check passes"                               make secrets-check

printf '\ngitignore\n'
printf 'CLEARTEXT=1\n' > secrets/prod/leak.env
git add -A >/dev/null 2>&1
expect_eq   "cleartext under a scope can't be staged"            "$(git diff --cached --name-only | grep -c 'leak.env$' || true)" "0"
expect_eq   "ciphertext is staged"                               "$(git diff --cached --name-only | grep -c '\.sops$')" "10"
rm secrets/prod/leak.env

printf '\nread\n'
expect_eq   "a service reads its own key"                        "$(as envprod make -s secrets-env FILE=prod/api.env KEY=DATABASE_PASSWORD)" "db_prod"
expect_eq   "  ...and shared.env's, layered under it"            "$(as envprod make -s secrets-env FILE=prod/api.env KEY=RESEND_API_KEY)" "re_prod"
expect_eq   "  ...shared keys first in the full dotenv"          "$(as envprod make -s secrets-env FILE=prod/api.env | cut -d= -f1 | tr '\n' ' ')" "RESEND_API_KEY DATABASE_PASSWORD "
expect_fail "a key in neither file fails"                        as envprod make -s secrets-env FILE=prod/api.env KEY=NOPE_TOKEN
expect_fail "a missing service file fails"                       as envprod make -s secrets-env FILE=prod/nope.env
expect_eq   "FORMAT=dotenv prints KEY=value"                     "$(as envprod make -s secrets-env FILE=prod/api.env KEY=RESEND_API_KEY FORMAT=dotenv)" "RESEND_API_KEY=re_prod"
expect_fail "actions key can't read prod/"                       as actions make -s secrets-env FILE=prod/api.env
expect_fail "env prod key can't read ci/"                        as envprod make -s secrets-env FILE=ci/deskhound.env
expect_fail "env prod key can't read terraform-prod/"            as envprod make -s secrets-env FILE=terraform-prod/terraform.env
expect_eq   "terraform-prod key reads the write token"           "$(as tfprod make -s secrets-env FILE=terraform-prod/terraform.env KEY=CLOUDFLARE_API_TOKEN)" "cf_write"
expect_fail "secrets-env refuses a bad KEY"                      as envprod make -s secrets-env FILE=prod/api.env 'KEY=a"]'

printf '\ndecrypt\n'
expect_fail "decrypt of a .env needs CONFIRM=1 off a tty"        make secrets-decrypt FILE=prod/api.env </dev/null
expect_ok   "decrypt with CONFIRM=1"                             make secrets-decrypt FILE=prod/api.env CONFIRM=1
expect_eq   "cleartext is mode 0600"                             "$(ls -l secrets/prod/api.env | cut -c1-10)" "-rw-------"
expect_ok   "decrypting again is a no-op"                        make secrets-decrypt FILE=prod/api.env CONFIRM=1
printf 'EXTRA_TOKEN=1\n' >> secrets/prod/api.env
expect_fail "decrypt refuses to overwrite an edited cleartext"   make secrets-decrypt FILE=prod/api.env CONFIRM=1
expect_ok   "binary decrypts without a prompt"                   as actions make secrets-decrypt FILE=ci/apple-distribution.p12 </dev/null
if cmp -s secrets/ci/apple-distribution.p12 "$work/p12.orig"; then pass "binary round-trips"; else fail "binary round-trips"; fi
printf 'NEW_TOKEN=1\n' > secrets/prod/worker.env
expect_fail "clean refuses cleartext with no ciphertext"         make secrets-clean
rm secrets/prod/worker.env
git checkout -q -- secrets 2>/dev/null; rm -f secrets/prod/api.env
expect_ok   "clean removes cleartext beside ciphertext"          make secrets-clean
expect_eq   "nothing left"                                       "$(find secrets -mindepth 2 -type f ! -name '*.sops' | wc -l | tr -d ' ')" "0"

printf '\ncheck failures\n'
cp secrets/prod/mcp.env.sops "$work/mcp.bak"
printf 'PLAIN_TOKEN=oops\n' >> secrets/prod/mcp.env.sops
expect_fail "check: plaintext value in a .sops file"             make secrets-check
expect_grep "  ...says so" "isn't encrypted"
cp "$work/mcp.bak" secrets/prod/mcp.env.sops
mv secrets/dev/mcp.env.sops "$work/devmcp.bak"
expect_fail "check: environments differ"                         make secrets-check
expect_grep "  ...says so" "don't have the same files and keys"
mv "$work/devmcp.bak" secrets/dev/mcp.env.sops
printf 'X_TOKEN=1\n' > secrets/prod/odd.env
(cd secrets && sops -e --config /dev/null --age "$(pub maint)" --input-type dotenv --output-type dotenv prod/odd.env > prod/odd.env.sops) 2>/dev/null
rm secrets/prod/odd.env
expect_fail "check: recipients differ from the scope rule"       make secrets-check
expect_grep "  ...says so" "recipients differ"
rm secrets/prod/odd.env.sops
for e in dev prod; do printf 'RESEND_API_KEY_PROD=x\n' > "secrets/$e/bad.env"; done
expect_ok   "encrypt a badly named key"                          make secrets-encrypt
expect_fail "check: key names an environment"                    make secrets-check
expect_grep "  ...says so" "names an environment"
rm secrets/dev/bad.env.sops secrets/prod/bad.env.sops
printf 'X_TOKEN=1\n' > secrets/ci/Bad_Name.env
make -s secrets-encrypt >/dev/null 2>&1
expect_fail "check: file name isn't kebab-case"                  make secrets-check
expect_grep "  ...says so" "lowercase kebab-case"
rm secrets/ci/Bad_Name.env.sops
cp secrets/.sops.yaml "$work/sops.bak"
printf '    encrypted_regex: ^x$\n' >> secrets/.sops.yaml
expect_fail "check: encrypted_regex is refused"                  make secrets-check
expect_grep "  ...says so" "leaves some values unencrypted"
cp "$work/sops.bak" secrets/.sops.yaml
expect_ok   "check passes again"                                 make secrets-check
expect_ok   "online check: private repo"                         make secrets-check ONLINE=1
expect_fail "online check: public repo fails"                    env GH_PRIVATE=false make secrets-check ONLINE=1
expect_grep "  ...says so" "isn't private"

printf '\nupdatekeys\n'
awk -v drop="$(pub envprod)" 'index($0, drop) == 0' "$work/sops.bak" > secrets/.sops.yaml
expect_fail "check sees the stale recipients"                    make secrets-check
expect_grep "  ...says so" "recipients differ"
expect_ok   "updatekeys SCOPE=prod ROTATE=1"                     make secrets-updatekeys SCOPE=prod ROTATE=1
expect_fail "the removed key no longer opens prod/"              as envprod make -s secrets-env FILE=prod/api.env
expect_ok   "check passes after updatekeys"                      make secrets-check
cp "$work/sops.bak" secrets/.sops.yaml
make secrets-updatekeys SCOPE=prod >/dev/null 2>&1

printf '\nmint\n'
expect_fail "mint needs CONFIRM_MINT"                            make secrets-mint CONTEXT=env-prod
expect_ok   "mint env-prod"                                      make secrets-mint CONTEXT=env-prod CONFIRM_MINT=1
expect_grep "  ...prints the public key"                         'public:   age1'
expect_grep "  ...names the identity"                            'identity: app__env-prod'
if grep -q 'AGE-SECRET-KEY' "$work/out"; then fail "  ...never prints the private key"; else pass "  ...never prints the private key"; fi
expect_eq   "  ...sends it to the prod environment"              "$(grep -c 'ARGS secret set SOPS_AGE_KEY -R o/app --env prod' "$GH_LOG")" "1"
expect_eq   "  ...on stdin"                                      "$(grep -c '^STDIN AGE-SECRET-KEY-' "$GH_LOG")" "1"
expect_ok   "mint actions uses --app"                            make secrets-mint CONTEXT=actions CONFIRM_MINT=1
expect_eq   "  ...--app actions"                                 "$(grep -c -- '--app actions' "$GH_LOG")" "1"
expect_fail "mint refuses an unknown context"                    make secrets-mint CONTEXT=cron CONFIRM_MINT=1

printf '\nsync\n'
for k in api__RESEND_API_KEY api__DATABASE_PASSWORD mcp__RESEND_API_KEY mcp__MCP_SIGNING_SECRET RESEND_API_KEY MCP_SIGNING_SECRET; do
    mkdir -p "$GCLOUD_STORE/demo-prod/$k"
done
sync_svc() { as envprod env GOOGLE_CLOUD_PROJECT=demo-prod make -s secrets-sync ENVIRONMENT=prod SERVICE="$1" CONFIRM_SYNC=1; }
reseal() {  # reseal FILE: replace a dotenv's contents with stdin
    make -s secrets-decrypt FILE="$1" CONFIRM=1 >/dev/null 2>&1
    cat > "secrets/$1"
    rm "secrets/$1.sops" && make -s secrets-encrypt FILE="$1" >/dev/null 2>&1
}
expect_fail "sync needs CONFIRM_SYNC"                            as envprod env GOOGLE_CLOUD_PROJECT=demo-prod make -s secrets-sync ENVIRONMENT=prod SERVICE=api
expect_eq   "sync layers shared.env, per-service store names"   "$(sync_svc api 2>/dev/null)" "DATABASE_PASSWORD=api__DATABASE_PASSWORD:1,RESEND_API_KEY=api__RESEND_API_KEY:1"
expect_eq   "  ...stores the shared value"                       "$(cat "$GCLOUD_STORE/demo-prod/api__RESEND_API_KEY/1")" "re_prod"
expect_eq   "a second sync adds nothing"                         "$(sync_svc api 2>/dev/null)" "DATABASE_PASSWORD=api__DATABASE_PASSWORD:1,RESEND_API_KEY=api__RESEND_API_KEY:1"
printf 'MCP_SIGNING_SECRET=mcp_prod\nRESEND_API_KEY=re_mcp\n' | reseal prod/mcp.env
expect_eq   "a service's own value overrides shared.env"         "$(sync_svc mcp 2>/dev/null)" "MCP_SIGNING_SECRET=mcp__MCP_SIGNING_SECRET:1,RESEND_API_KEY=mcp__RESEND_API_KEY:1"
expect_eq   "  ...its copy holds the override"                   "$(cat "$GCLOUD_STORE/demo-prod/mcp__RESEND_API_KEY/1")" "re_mcp"
expect_eq   "  ...api's copy is untouched"                       "$(ls "$GCLOUD_STORE/demo-prod/api__RESEND_API_KEY" | wc -l | tr -d ' ')" "1"
expect_eq   "  ...secrets-env layers the same way"               "$(as envprod make -s secrets-env FILE=prod/mcp.env KEY=RESEND_API_KEY)" "re_mcp"
expect_fail "sync refuses SERVICE=shared"                        sync_svc shared
expect_eq   "STORE_PREFIX= keeps bare store names"              "$(as envprod env STORE_PREFIX= GOOGLE_CLOUD_PROJECT=demo-prod make -s secrets-sync ENVIRONMENT=prod SERVICE=mcp CONFIRM_SYNC=1 2>/dev/null)" "MCP_SIGNING_SECRET=MCP_SIGNING_SECRET:1,RESEND_API_KEY=RESEND_API_KEY:1"
printf 'RESEND_API_KEY=@estate\n' | reseal prod/shared.env
mkdir -p "$work/estate/prod"
printf 'RESEND_API_KEY=re_estate\n' > "$work/estate/prod/backend.env"
sops -e --config /dev/null --age "$(pub envprod)" --input-type dotenv --output-type dotenv "$work/estate/prod/backend.env" > "$work/estate/prod/backend.env.sops"
rm "$work/estate/prod/backend.env"
expect_ok   "sync resolves @estate in shared.env"                as envprod env GOOGLE_CLOUD_PROJECT=demo-prod ESTATE_DIST="$work/estate" make -s secrets-sync ENVIRONMENT=prod SERVICE=api CONFIRM_SYNC=1
expect_eq   "  ...writes the estate value"                       "$(cat "$GCLOUD_STORE/demo-prod/api__RESEND_API_KEY/2")" "re_estate"
expect_fail "@estate with no estate checkout fails"              sync_svc api
expect_fail "sync refuses a missing store secret"                as envdev env GOOGLE_CLOUD_PROJECT=demo-dev make -s secrets-sync ENVIRONMENT=dev SERVICE=api CONFIRM_SYNC=1
expect_fail "sync refuses a scope that isn't a deploy environment" as tfprod env GOOGLE_CLOUD_PROJECT=demo-prod make -s secrets-sync ENVIRONMENT=terraform-prod SERVICE=terraform CONFIRM_SYNC=1

printf '\nfacts\n'
expect_ok   "secrets-facts runs in a single repo"                bash "$here/../scripts/secrets-facts.sh"
expect_grep "  ...sees a single repo"                            'kind: single repo'
if grep -q 'AGE-SECRET-KEY' "$work/out"; then fail "secrets-facts printed a private key"; else pass "  ...prints no private key"; fi
if grep -q 're_prod\|cf_write\|p12pass' "$work/out"; then fail "secrets-facts printed a secret value"; else pass "  ...prints no secret value"; fi

printf '\n'
if [ "$failures" -eq 0 ]; then echo "test-single-repo: all passed"; else echo "test-single-repo: $failures failed"; exit 1; fi
