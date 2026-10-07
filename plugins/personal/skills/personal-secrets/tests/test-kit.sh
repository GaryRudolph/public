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
unset SOPS_AGE_KEY SOPS_AGE_KEY_CMD
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
expect_fail "mint refuses an existing identity"    make mint REPO=app CONTEXT=actions
expect_fail "mint refuses an unknown context"      make mint REPO=app CONTEXT=cron
expect_fail "mint refuses a bad repo name"         make mint REPO='a b' CONTEXT=actions
expect_eq   "no plaintext registry on disk"        "$(ls keys)" "repos.env.sops"

cat > access.map <<'EOF'
@oss        = site__actions app__actions app__agents
@commercial = app__actions

oss.env:         @oss
commercial.env:  @commercial
ios/AuthKey.p8:  app__actions
EOF
mkdir -p src/ios
printf 'PUBLIC_API_URL=https://api.example.com\nSHARED=oss\n' > src/oss.env
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

printf '\nconsumers\n'
expect_eq   "KEY lookup, raw value"               "$(as_consumer "$site" make -s dist-decrypt-env KEY=PUBLIC_API_URL)" "https://api.example.com"
expect_eq   "KEY + FORMAT=dotenv"                 "$(as_consumer "$site" make -s dist-decrypt-env KEY=PUBLIC_API_URL FORMAT=dotenv)" "PUBLIC_API_URL=https://api.example.com"
expect_fail "site can't read commercial.env"      as_consumer "$site" make -s dist-decrypt-env FILE=commercial.env
expect_fail "KEY in two files needs FILE="         as_consumer "$app" make -s dist-decrypt-env KEY=SHARED
expect_eq   "FILE= disambiguates"                  "$(as_consumer "$app" make -s dist-decrypt-env FILE=commercial.env KEY=SHARED)" "commercial"
expect_fail "KEY must be a variable name"         as_consumer "$app" make -s dist-decrypt-env KEY='.*'
expect_fail "agents can't read the signing key"   as_consumer "$agents" make -s dist-decrypt FILE=ios/AuthKey.p8
expect_ok   "app decrypts the signing key"         as_consumer "$app" make -s dist-decrypt FILE=ios/AuthKey.p8
expect_ok   "binary round-trips"                   cmp dist/ios/AuthKey.p8 "$work/p8.orig"
expect_eq   "decrypted file is owner-only"         "$(stat -c '%a' dist/ios/AuthKey.p8 2>/dev/null || stat -f '%Lp' dist/ios/AuthKey.p8)" "600"
expect_ok   "all-env export skips what it can't open" as_consumer "$site" make -s dist-decrypt-env
expect_grep "  ...and emits only oss.env"          "PUBLIC_API_URL="
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
expect_eq   "  ...three stores"                    "$(grep -c '^ARGS' "$GH_LOG")" "3"

sed -i.bak 's/ app__agents//' access.map && rm access.map.bak
make -s build >/dev/null
expect_ok   "retire once ungranted"                make retire REPO=app CONTEXT=agents
expect_ok   "verify at the end"                    make verify

printf '\nfacts\n'
make -s src-decrypt FILE=oss.env >/dev/null
expect_ok   "secrets-facts runs in a secrets repo" bash "$here/../scripts/secrets-facts.sh"
expect_grep "  ...lists registry identities"        "app__actions"
expect_grep "  ...reports plaintext on disk"        "plaintext on disk: src/oss.env"
if grep -q 'AGE-SECRET-KEY' "$work/out"; then fail "secrets-facts printed a private key"; else pass "  ...prints no private key"; fi
if grep -q 'api.example.com' "$work/out"; then fail "secrets-facts printed a secret value"; else pass "  ...prints no secret value"; fi
make -s clean >/dev/null

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf 'test-kit: %d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'test-kit: all passed\n'
