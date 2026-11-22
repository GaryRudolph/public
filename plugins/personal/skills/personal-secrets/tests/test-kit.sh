#!/usr/bin/env bash
# End-to-end test of templates/secrets-repo in a sandbox estate. Needs sops,
# age, and age-keygen on PATH; skips cleanly without them. Stubs gh, so
# nothing reaches GitHub. Runs every script under bash 3.2 when /bin/bash is
# 3.2 (macOS), which is what maintainers on a Mac get.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
kit="$here/../templates/secrets-repo"

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

# --- sandbox: bash 3.2 first on PATH, stub gh that records its calls --------
mkdir -p "$work/bin" "$work/keys" "$work/home"
[ -x /bin/bash ] && ln -s /bin/bash "$work/bin/bash"
cat > "$work/bin/gh" <<'EOF'
#!/bin/sh
printf 'ARGS %s\n' "$*" >> "$GH_LOG"
# Only `gh secret set` takes the value on stdin; anything else must not block.
case "$1 $2" in
    "secret set") printf 'STDIN %s\n' "$(cat)" >> "$GH_LOG" ;;
    *) echo "gh stub" ;;
esac
EOF
chmod +x "$work/bin/gh"
export PATH="$work/bin:$PATH" GH_LOG="$work/gh.log" HOME="$work/home" XDG_CONFIG_HOME="$work/home"
# Fixture repos read only their own config: the host's hooks, signing and
# includes (a runner sets core.hooksPath) would change the commits under test.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
# A parent make (make -C agents test) exports -w through MAKEFLAGS, which
# would print "Entering directory" into captured output.
unset MAKEFLAGS MAKELEVEL MFLAGS
unset SOPS_AGE_KEY SOPS_AGE_KEY_CMD
# Masking is tested explicitly below; elsewhere run as a workstation would.
unset GITHUB_ACTIONS
printf 'bash under test: %s\n' "$(bash -c 'echo $BASH_VERSION')"

age-keygen -o "$work/keys/maint.txt" 2>/dev/null
age-keygen -o "$work/keys/bg.txt" 2>/dev/null
maint_pub=$(age-keygen -y "$work/keys/maint.txt")
bg_pub=$(age-keygen -y "$work/keys/bg.txt")
export SOPS_AGE_KEY_FILE="$work/keys/maint.txt"

repo="$work/estate-secrets"
cp -R "$kit" "$repo"
cd "$repo" || exit 1
git init -q && git config user.email t@example.com && git config user.name test
printf '%s\n' "$bg_pub" > breakglass.pub
sed -i.bak -e "s/<maintainer-age-public-key>/$maint_pub/" -e "s/<breakglass-age-public-key>/$bg_pub/" .sops.yaml && rm .sops.yaml.bak

consumer_key() {
    SOPS_AGE_KEY_FILE="$work/keys/maint.txt" sops -d --input-type dotenv --output-type dotenv keys/repos.env.sops \
        | awk -v k="$1__private=" 'index($0, k) == 1 { print substr($0, length(k) + 1) }'
}
as_consumer() {
    local key="$1"
    shift
    env -u SOPS_AGE_KEY_FILE SOPS_AGE_KEY="$key" "$@"
}

printf '\nsetup\n'
expect_ok   "make init wires the hook"            make init
expect_eq   "hooksPath is .githooks"              "$(git config core.hooksPath)" ".githooks"
expect_ok   "mint app__actions"                    make mint REPO=app CONTEXT=actions
expect_ok   "mint app__agents"                     make mint REPO=app CONTEXT=agents
expect_ok   "mint site__actions"                   make mint REPO=site CONTEXT=actions
expect_ok   "mint app__env-prod"                   make mint REPO=app CONTEXT=env-prod
expect_fail "mint refuses an empty environment"    make mint REPO=app CONTEXT=env-
expect_fail "mint refuses __ in an environment"    make mint REPO=app CONTEXT=env-a__b
expect_fail "mint refuses a bad environment name"  make mint REPO=app CONTEXT='env-a b'
expect_fail "mint refuses an existing identity"    make mint REPO=app CONTEXT=actions
expect_fail "mint refuses an unknown context"      make mint REPO=app CONTEXT=cron
expect_fail "mint refuses a bad repo name"         make mint REPO='a b' CONTEXT=actions
expect_eq   "no plaintext registry on disk"        "$(ls keys)" "repos.env.sops"

cat > access.map <<'EOF'
@oss        = site__actions app__actions app__agents
@commercial = app__actions
@prod       = app__env-prod

oss.env:         @oss
commercial.env:  @commercial
ios/AuthKey.p8:  app__actions
prod/email.env:  @prod
EOF
mkdir -p src/ios src/prod
printf 'RESEND_API_KEY=re_prod_test\n' > src/prod/email.env
# MULTI is a multi-line value as dotenv stores it (\n escaped), with a line
# too short to mask alone and a %0A the runner would decode if the mask
# weren't percent-encoded. WORD's value is the mask helper's mode name.
# SPACED is quoted after a space; CRLF holds a CR before its \n.
printf 'AUTH_TOKEN=token_oss_test\nSHARED=oss\nMULTI=line1\\n{\\nline2%%0Aend\nWORD=dotenv\nSPACED= "quoted-secret"\nCRLF=first-line\r\\nsecond-line\n' > src/oss.env
printf 'STRIPE_KEY=sk_live_x\nSHARED=commercial\n' > src/commercial.env
head -c 512 /dev/urandom > src/ios/AuthKey.p8
cp src/ios/AuthKey.p8 "$work/p8.orig"

expect_ok   "src-encrypt"                          make src-encrypt
expect_eq   "plaintext removed after encrypt"      "$(find src -type f ! -name '*.sops' ! -name .gitkeep | wc -l | tr -d ' ')" "0"
expect_ok   "build"                                make build
expect_ok   "lint (keyless)"                       make lint
expect_ok   "verify"                               make verify

app=$(consumer_key app__actions)
agents=$(consumer_key app__agents)
site=$(consumer_key site__actions)
envprod=$(consumer_key app__env-prod)

printf '\nconsumers\n'
expect_eq   "KEY lookup, raw value"               "$(as_consumer "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN)" "token_oss_test"
expect_eq   "KEY + FORMAT=dotenv"                 "$(as_consumer "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv)" "AUTH_TOKEN=token_oss_test"
expect_fail "site can't read commercial.env"      as_consumer "$site" make -s dist-decrypt-env FILE=commercial.env
expect_fail "KEY in two files needs FILE="         as_consumer "$app" make -s dist-decrypt-env KEY=SHARED
expect_eq   "FILE= disambiguates"                  "$(as_consumer "$app" make -s dist-decrypt-env FILE=commercial.env KEY=SHARED)" "commercial"
expect_fail "KEY must be a variable name"         as_consumer "$app" make -s dist-decrypt-env KEY='.*'
expect_fail "agents can't read the signing key"   as_consumer "$agents" make -s dist-decrypt FILE=ios/AuthKey.p8
expect_ok   "app decrypts the signing key"         as_consumer "$app" make -s dist-decrypt FILE=ios/AuthKey.p8
expect_ok   "binary round-trips"                   cmp dist/ios/AuthKey.p8 "$work/p8.orig"
expect_eq   "decrypted file is owner-only"         "$(stat -c '%a' dist/ios/AuthKey.p8 2>/dev/null || stat -f '%Lp' dist/ios/AuthKey.p8)" "600"
expect_eq   "env-prod key reads its file"          "$(as_consumer "$envprod" make -s dist-decrypt-env FILE=prod/email.env KEY=RESEND_API_KEY)" "re_prod_test"
expect_fail "env-prod key can't read ci files"     as_consumer "$envprod" make -s dist-decrypt-env FILE=commercial.env
expect_fail "actions key can't read prod/"         as_consumer "$app" make -s dist-decrypt-env FILE=prod/email.env
expect_ok   "all-env export skips what it can't open" as_consumer "$site" make -s dist-decrypt-env
expect_grep "  ...and emits only oss.env"          "AUTH_TOKEN="

printf '\nmasking under Actions\n'
gha() { local key="$1"; shift; as_consumer "$key" env GITHUB_ACTIONS=true "$@"; }
masks() { grep '^::add-mask::' || true; }
expect_eq   "raw value: stdout is the value alone"  "$(gha "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN 2>/dev/null)" "token_oss_test"
expect_eq   "  ...and the mask is on stderr"        "$(gha "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN 2>&1 >/dev/null | masks)" "::add-mask::token_oss_test"
expect_eq   "  ...on a fresh line, before the value" "$(gha "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv 2>&1 | tr '\n' ' ')" " ::add-mask::token_oss_test AUTH_TOKEN=token_oss_test "
expect_eq   "  ...even after an unterminated line"  "$( { printf 'progress' >&2; gha "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN; } 2>&1 >/dev/null | masks)" "::add-mask::token_oss_test"
expect_eq   "dotenv line: stdout unchanged"         "$(gha "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv 2>/dev/null)" "AUTH_TOKEN=token_oss_test"
expect_eq   "FILE= + KEY masks too"                 "$(gha "$app" make -s dist-decrypt-env FILE=commercial.env KEY=SHARED 2>&1 >/dev/null | masks)" "::add-mask::commercial"
expect_eq   "multi-line value: whole, then each long line, %-encoded" \
    "$(gha "$site" make -s dist-decrypt-env KEY=MULTI 2>&1 >/dev/null | masks | tr '\n' ' ')" \
    '::add-mask::line1\n{\nline2%250Aend ::add-mask::line1 ::add-mask::line2%250Aend '
expect_eq   "  ...stdout still the stored value"    "$(gha "$site" make -s dist-decrypt-env KEY=MULTI 2>/dev/null)" 'line1\n{\nline2%0Aend'
expect_eq   "a value that names the mask mode"      "$(gha "$site" make -s dist-decrypt-env KEY=WORD 2>&1 | tr '\n' ' ')" " ::add-mask::dotenv dotenv"
expect_eq   "a spaced, quoted value: as printed, trimmed, unquoted" \
    "$(gha "$site" make -s dist-decrypt-env KEY=SPACED 2>&1 >/dev/null | masks | tr '\n' '|')" \
    '::add-mask:: "quoted-secret"|::add-mask::"quoted-secret"|::add-mask::quoted-secret|'
expect_eq   "a CRLF value: each line without its CR" \
    "$(gha "$site" make -s dist-decrypt-env KEY=CRLF 2>&1 >/dev/null | masks | tr '\n' '|')" \
    '::add-mask::first-line%0D\nsecond-line|::add-mask::first-line|::add-mask::second-line|'
gha "$site" make -s dist-decrypt-env >"$work/all.out" 2>"$work/all.err"
unmasked=""
while IFS= read -r line; do
    v=${line#*=}
    grep -qxF "::add-mask::$(printf '%s' "$v" | sed -e 's/%/%25/g' -e "s/$(printf '\r')/%0D/g")" "$work/all.err" || unmasked="$unmasked ${line%%=*}"
done < "$work/all.out"
expect_eq   "export-all: every value printed is masked" "$unmasked" ""
expect_eq   "  ...and it printed values"            "$(grep -c '=' "$work/all.out")" "6"
gha "$site" make -s dist-decrypt-env FILE=oss.env >"$work/out" 2>&1
expect_grep "FILE= export masks"                    "^::add-mask::token_oss_test$"
expect_eq   "no masks outside Actions"              "$(as_consumer "$site" make -s dist-decrypt-env KEY=AUTH_TOKEN 2>&1 >/dev/null | masks)" ""
make -s clean >/dev/null

printf '\ncommits\n'
git add -A
expect_ok   "commit of a clean build passes the hook" git commit -qm build
printf 'leak\n' > src/leak.txt
git add -f src/leak.txt
expect_fail "hook refuses staged plaintext"       git commit -qm leak
git rm -q --cached src/leak.txt && rm src/leak.txt

make -s src-decrypt FILE=oss.env >/dev/null
printf 'NEW=1\n' >> src/oss.env
make -s src-encrypt FILE=oss.env >/dev/null
expect_fail "verify catches a stale dist/"         make verify
expect_grep "  ...and says it's stale"             "stale"
git add src/oss.env.sops
expect_fail "hook refuses src/ without dist/"      git commit -qm stale
expect_ok   "rebuild"                              make build
git add -A
expect_ok   "commit with dist/ passes the hook"    git commit -qm fresh
expect_ok   "ci --range passes for that commit"    make ci RANGE=HEAD~1..HEAD

printf '\ncheck fails closed\n'
mkdir -p "$work/nogit" "$work/nofind"
printf '#!/bin/sh\nexit 2\n' > "$work/nogit/git"
printf '#!/bin/sh\nexit 2\n' > "$work/nofind/find"
chmod +x "$work/nogit/git" "$work/nofind/find"
expect_fail "lint: git can't list tracked files"    env PATH="$work/nogit:$PATH" make lint
expect_grep "  ...says so"                          "cannot list tracked files: git ls-files failed"
expect_fail "lint: find can't list src/ or dist/"   env PATH="$work/nofind:$PATH" make lint
expect_grep "  ...names src/"                       "cannot list src/: find failed"
expect_grep "  ...and dist/"                        "cannot list dist/: find failed"
expect_fail "ci: git can't diff the range"          env PATH="$work/nogit:$PATH" make ci RANGE=HEAD~1..HEAD
expect_grep "  ...says so"                          "cannot list changes in HEAD~1..HEAD: git diff failed"
expect_fail "ci: a range git can't resolve fails"   make ci RANGE=no-such-base..HEAD
expect_grep "  ...names the range"                  "cannot list changes in no-such-base..HEAD"
expect_fail "hook: git can't list staged changes"   env PATH="$work/nogit:$PATH" bash scripts/check.sh --staged
expect_grep "  ...says so"                          "cannot list staged changes: git diff --cached failed"
expect_fail "consumer: find can't list dist/"       as_consumer "$site" env PATH="$work/nofind:$PATH" make -s dist-decrypt-env KEY=AUTH_TOKEN
expect_grep "  ...says so"                          "cannot list dist/'s env files: find failed"
expect_fail "consumer export: find can't list dist/" as_consumer "$site" env PATH="$work/nofind:$PATH" make -s dist-decrypt-env
expect_grep "  ...says so"                          "cannot list dist/'s env files: find failed"
# A fresh estate whose src/ and dist/ don't exist yet has nothing to list:
# that's empty, not a failure.
fresh="$work/fresh"
cp -R "$kit" "$fresh"
rm -rf "$fresh/src" "$fresh/dist"
printf '%s\n' "$bg_pub" > "$fresh/breakglass.pub"
sed -i.bak "s/<breakglass-age-public-key>/$bg_pub/" "$fresh/.sops.yaml" && rm "$fresh/.sops.yaml.bak"
git -C "$fresh" init -q
expect_ok   "lint: no src/ or dist/ lists as empty"  make --no-print-directory -C "$fresh" lint
expect_grep "  ...says ok"                          "check: ok"
expect_ok   "lint passes with the real tools"       make lint
expect_grep "  ...says ok"                          "check: ok"
expect_ok   "ci passes with the real tools"         make ci RANGE=HEAD~1..HEAD
# An orphan whose name is a glob matching a mapped file (oss.env.sops) must
# be checked under its own name, not the file the glob expands to.
cp src/oss.env.sops 'src/[co]ss.env.sops'
expect_fail "lint: a glob-named orphan is caught"   make lint
expect_grep "  ...under its own name"               'src/\[co\]ss.env.sops is not listed'
rm 'src/[co]ss.env.sops'

printf '\naccess changes\n'
sed -i.bak 's/^@oss        = site__actions /@oss        = /' access.map && rm access.map.bak
git add access.map
expect_fail "hook refuses access.map without a rebuild" git commit -qm revoke
expect_ok   "build after revoking site"            make build
expect_fail "site lost oss.env"                    as_consumer "$site" make -s dist-decrypt-env FILE=oss.env
expect_ok   "verify after revoke"                  make verify
git add -A && git commit -qm revoke >/dev/null

# Over-sharing: publish oss.env to site behind access.map's back.
site_pub=$(SOPS_AGE_KEY_FILE="$work/keys/maint.txt" sops -d --input-type dotenv --output-type dotenv keys/repos.env.sops | sed -n 's/^site__actions__public=//p')
sops -d --input-type dotenv --output-type dotenv src/oss.env.sops \
    | sops --config /dev/null -e --age "$bg_pub,$site_pub" --input-type dotenv --output-type dotenv /dev/stdin > dist/oss.env.sops
expect_fail "verify catches over-sharing"          make verify
expect_grep "  ...and names the identity"          "site__actions can decrypt dist/oss.env.sops"
make -s build >/dev/null

expect_fail "retire refuses a granted identity"   make retire REPO=app CONTEXT=agents
old_app=$app
expect_ok   "rotate app__actions"                  make rotate REPO=app CONTEXT=actions
expect_ok   "build after rotate"                   make build
app=$(consumer_key app__actions)
expect_fail "old key stops working"                as_consumer "$old_app" make -s dist-decrypt-env FILE=commercial.env
expect_ok   "new key works"                        as_consumer "$app" make -s dist-decrypt-env FILE=commercial.env
expect_fail "rotate refuses an unknown identity"  make rotate REPO=nope CONTEXT=actions

sed -i.bak '/^ios\/AuthKey.p8:/d' access.map && rm access.map.bak
expect_fail "lint flags the now-unmapped src file" make lint
rm src/ios/AuthKey.p8.sops
expect_ok   "build removes the unmapped dist file" make build
expect_eq   "  ...dist/ios is empty"               "$(find dist/ios -type f 2>/dev/null | wc -l | tr -d ' ')" "0"

printf 'broken.env: app__cron\n' >> access.map
expect_fail "lint rejects an unknown context"      make lint
sed -i.bak '/^broken.env:/d' access.map && rm access.map.bak
printf 'broken.env: @missing\n' >> access.map
expect_fail "lint rejects an undefined group"      make lint
sed -i.bak '/^broken.env:/d' access.map && rm access.map.bak

printf '\nset-keys\n'
expect_fail "set-keys needs CONFIRM_SET_KEYS=1"   make set-keys
expect_fail "set-keys needs a real OWNER"          make set-keys CONFIRM_SET_KEYS=1
: > "$GH_LOG"
expect_ok   "set-keys for one identity"            make set-keys CONFIRM_SET_KEYS=1 OWNER=acme REPO=app CONTEXT=actions
expect_eq   "gh called once, with the right store" "$(grep '^ARGS' "$GH_LOG")" "ARGS secret set SOPS_AGE_KEY -R acme/app --app actions"
expect_eq   "key went over stdin"                  "$(sed -n 's/^STDIN //p' "$GH_LOG")" "$app"
if grep '^ARGS' "$GH_LOG" | grep -q AGE-SECRET-KEY; then fail "private key appeared in gh's arguments"; else pass "private key never in argv"; fi
: > "$GH_LOG"
expect_ok   "set-keys for all"                     make set-keys CONFIRM_SET_KEYS=1 OWNER=acme
expect_eq   "  ...four stores"                     "$(grep -c '^ARGS' "$GH_LOG")" "4"
expect_eq   "  ...env-prod goes to the environment" "$(grep -c '^ARGS secret set SOPS_AGE_KEY -R acme/app --env prod$' "$GH_LOG")" "1"
: > "$GH_LOG"
expect_ok   "set-keys for one environment context" make set-keys CONFIRM_SET_KEYS=1 OWNER=acme REPO=app CONTEXT=env-prod
expect_eq   "  ...uses --env, once"                "$(grep '^ARGS' "$GH_LOG")" "ARGS secret set SOPS_AGE_KEY -R acme/app --env prod"
expect_eq   "  ...key over stdin"                  "$(sed -n 's/^STDIN //p' "$GH_LOG")" "$envprod"
expect_fail "set-keys refuses a bad context"       make set-keys CONFIRM_SET_KEYS=1 OWNER=acme CONTEXT=env-

sed -i.bak 's/ app__agents//' access.map && rm access.map.bak
make -s build >/dev/null
expect_ok   "retire once ungranted"                make retire REPO=app CONTEXT=agents
sed -i.bak -e '/^@prod /d' -e '/^prod\/email.env:/d' access.map && rm access.map.bak
rm src/prod/email.env.sops
make -s build >/dev/null
expect_ok   "retire an environment context"        make retire REPO=app CONTEXT=env-prod
expect_grep "  ...hints gh secret delete --env"    "gh secret delete SOPS_AGE_KEY -R <owner>/app --env prod"
expect_ok   "verify at the end"                    make verify

printf '\nfacts\n'
make -s src-decrypt FILE=oss.env >/dev/null
expect_ok   "secrets-facts runs in a secrets repo" bash "$here/../scripts/secrets-facts.sh"
expect_grep "  ...lists registry identities"        "app__actions"
expect_grep "  ...reports plaintext on disk"        "plaintext on disk: src/oss.env"
if grep -q 'AGE-SECRET-KEY' "$work/out"; then fail "secrets-facts printed a private key"; else pass "  ...prints no private key"; fi
if grep -q 'token_oss_test' "$work/out"; then fail "secrets-facts printed a secret value"; else pass "  ...prints no secret value"; fi
make -s clean >/dev/null

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf 'test-kit: %d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'test-kit: all passed\n'
