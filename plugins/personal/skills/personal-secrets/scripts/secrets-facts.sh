#!/usr/bin/env bash
# Facts for the personal-secrets skill. Run from a secrets repo or a consumer
# repo. Prints names, paths, and check results; never a secret value or a
# private key. Makes no recommendations: the agent decides what to do.
set -uo pipefail

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$root" || exit 1

section() { printf '\n== %s\n' "$1"; }

section tools
for t in sops age age-keygen gh git; do
    if command -v "$t" >/dev/null 2>&1; then
        printf '  %-11s %s\n' "$t" "$("$t" --version </dev/null 2>&1 | head -1)"
    else
        printf '  %-11s missing\n' "$t"
    fi
done
printf '  %-11s %s\n' bash "$(bash -c 'echo $BASH_VERSION')"

section "age key sources (names only)"
[ -n "${SOPS_AGE_KEY:-}" ] && echo "  SOPS_AGE_KEY is set" || echo "  SOPS_AGE_KEY not set"
if [ -n "${SOPS_AGE_KEY_FILE:-}" ]; then
    [ -f "$SOPS_AGE_KEY_FILE" ] && echo "  SOPS_AGE_KEY_FILE=$SOPS_AGE_KEY_FILE (exists)" || echo "  SOPS_AGE_KEY_FILE=$SOPS_AGE_KEY_FILE (missing)"
else
    echo "  SOPS_AGE_KEY_FILE not set"
fi
for f in "${XDG_CONFIG_HOME:-$HOME/.config}/sops/age/keys.txt" "$HOME/Library/Application Support/sops/age/keys.txt"; do
    [ -f "$f" ] && echo "  default key file present: $f"
done

section repo
printf '  root: %s\n' "$root"
printf '  remote: %s\n' "$(git remote get-url origin 2>/dev/null || echo none)"
printf '  branch: %s\n' "$(git branch --show-current 2>/dev/null || echo none)"

if [ -f access.map ] && [ -f .sops.yaml ]; then
    printf '  kind: secrets repo\n'

    section "secrets repo"
    printf '  OWNER in Makefile: %s\n' "$(sed -n 's/^OWNER ?= //p' Makefile 2>/dev/null || echo '?')"
    printf '  hooksPath: %s\n' "$(git config core.hooksPath || echo unset)"
    printf '  source recipients in .sops.yaml: %s\n' "$(grep -o 'age1[0-9a-z]*' .sops.yaml | sort -u | wc -l | tr -d ' ')"
    grep -q '<.*-age-public-key>' .sops.yaml && echo "  .sops.yaml still has placeholder keys"
    [ -f breakglass.pub ] && echo "  breakglass.pub present" || echo "  breakglass.pub missing"

    section "access.map (groups expanded)"
    if [ -f scripts/lib.sh ]; then
        ( . scripts/lib.sh && access_entries ) 2>&1 | sed 's/^/  /'
    else
        sed 's/^/  /' access.map
    fi

    section "files"
    printf '  src:  %s\n' "$(find src -type f -name '*.sops' 2>/dev/null | sort | tr '\n' ' ')"
    printf '  dist: %s\n' "$(find dist -type f -name '*.sops' 2>/dev/null | sort | tr '\n' ' ')"
    plain=$(find src dist keys -type f ! -name '*.sops' ! -name '.gitkeep' 2>/dev/null | sort | tr '\n' ' ')
    printf '  plaintext on disk: %s\n' "${plain:-none}"

    section "registry identities (names only)"
    if [ -f keys/repos.env.sops ]; then
        if ids=$(sops -d --input-type dotenv --output-type dotenv keys/repos.env.sops </dev/null 2>/dev/null | sed -n 's/__public=.*$//p' | sort); then
            [ -n "$ids" ] && printf '%s\n' "$ids" | sed 's/^/  /' || echo "  (empty)"
        else
            echo "  can't decrypt with the keys available here (needs a maintainer key)"
        fi
    else
        echo "  keys/repos.env.sops doesn't exist yet"
    fi

    section "keyless check"
    if [ -f scripts/check.sh ]; then
        bash scripts/check.sh 2>&1 | sed 's/^/  /'
    else
        echo "  scripts/check.sh missing (repo predates the kit)"
    fi

    section "recent commits touching src/ dist/ access.map"
    git log --oneline -5 -- src dist access.map 2>/dev/null | sed 's/^/  /'
else
    printf '  kind: consumer or other repo\n'

    section "consumer wiring"
    name=$(basename "$(git remote get-url origin 2>/dev/null || echo "$root")" .git)
    printf '  repo name: %s (identities would be %s__<context>)\n' "$name" "$name"
    if [ -d .github/workflows ]; then
        for f in .github/workflows/*.y*ml; do
            [ -f "$f" ] || continue
            hits=$(grep -nE 'SOPS_AGE_KEY|dist-decrypt|create-github-app-token|-secrets|setup-sops' "$f" | cut -c1-120)
            [ -n "$hits" ] && { printf '  %s\n' "$f"; printf '%s\n' "$hits" | sed 's/^/    /'; }
        done
    else
        echo "  no .github/workflows"
    fi
    if git check-ignore -q .env 2>/dev/null; then echo "  .env is gitignored"; else echo "  .env is NOT gitignored"; fi
    tracked_env=$(git ls-files | grep -E '(^|/)\.env($|\.)' | grep -v '\.example$' || true)
    [ -n "$tracked_env" ] && printf '  tracked env files: %s\n' "$(printf '%s ' $tracked_env)"
    if command -v gh >/dev/null 2>&1; then
        for app in actions agents codespaces dependabot; do
            names=$(gh secret list --app "$app" </dev/null 2>/dev/null | awk '{print $1}' | tr '\n' ' ')
            printf '  gh secrets (%s): %s\n' "$app" "${names:-none or no access}"
        done
    fi
fi
