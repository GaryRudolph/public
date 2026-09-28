# <estate>-secrets Makefile
#
# SOPS + age secrets repository. Maintainer targets need a source (maintainer
# or break-glass) age key; consumer targets need only that consumer's
# SOPS_AGE_KEY; `ci` needs no key at all.
#
# Conventions:
#   - `.DEFAULT_GOAL := help`; bare `make` prints grouped targets.
#   - Self-documenting: `## comment` after a target; `##@ Section` for headers.
#   - Remote-mutating targets under `##@ Danger` with CONFIRM_* guards.
#
# See Makefile.md for the narrative reference, and the personal secrets
# standard (standards/secrets/) for the architecture.

SHELL := bash

.DEFAULT_GOAL := help

.PHONY: help init doctor build lint format test ci pre-commit clean \
        src-decrypt src-encrypt mint rotate retire verify \
        dist-decrypt-env dist-decrypt \
        gh-runs-list gh-runs-watch gh-runs-status bump set-keys

# GitHub org or user that owns the consumer repos (used by set-keys).
OWNER ?= <org>
GH_LIMIT ?= 50
# Commit range for `make ci` in CI, e.g. RANGE=origin/main..HEAD.
RANGE ?=
TOOLS := sops age age-keygen gh git

confirm = @if [ -z "$($(1))" ]; then \
  printf 'Refusing to run "make %s": %s\nRe-run with %s=1.\n' "$@" "$(2)" "$(1)"; \
  exit 1; \
fi

##@ Develop

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0,5)}' $(MAKEFILE_LIST)

init: ## Wire the pre-commit hook, make scripts executable, run doctor (idempotent)
	@git config core.hooksPath .githooks
	@chmod +x .githooks/pre-commit scripts/*.sh dist-decrypt-env.sh dist-decrypt.sh
	@$(MAKE) --no-print-directory doctor

doctor: ## Check required tools (read-only)
	@missing=0; for t in $(TOOLS); do \
	  if command -v $$t >/dev/null 2>&1; then printf '  ok       %s\n' "$$t"; \
	  else printf '  missing  %s\n' "$$t"; missing=1; fi; \
	done; \
	[ "$$(git config core.hooksPath)" = .githooks ] && printf '  ok       pre-commit hook\n' || printf '  missing  pre-commit hook (make init)\n'; \
	exit $$missing

build: ## Re-encrypt src/ to dist/ for each file's recipients in access.map (source key)
	@bash scripts/build.sh

lint: ## Keyless checks: access.map, file pairing, no tracked plaintext, break-glass
	@bash scripts/check.sh

format: ## No-op: no formatter for sops ciphertext or access.map

test: verify ## Full verification with consumer keys (alias of verify; source key)

ci: ## Keyless gate CI runs; RANGE=<base>..<head> also checks src/dist pairing
	@if [ -n "$(RANGE)" ]; then bash scripts/check.sh --range "$(RANGE)"; else bash scripts/check.sh; fi

pre-commit: ci ## Run the local gate before committing or pushing (alias of ci)

clean: ## Delete decrypted plaintext siblings under src/ and dist/
	@find src dist -type f ! -name '*.sops' ! -name '.gitkeep' -print -delete 2>/dev/null || true

##@ Secrets

src-decrypt: ## Decrypt src/ for editing (source key). FILE=<logical path> for one
	@bash scripts/crypt.sh decrypt "$(FILE)"

src-encrypt: ## Encrypt edited src/ plaintext back to .sops and delete it. FILE= for one
	@bash scripts/crypt.sh encrypt "$(FILE)"

mint: ## New consumer keypair (source key). REPO= CONTEXT=actions|agents|codespaces|dependabot
	@bash scripts/keys.sh mint "$(REPO)" "$(CONTEXT)"

rotate: ## Replace a consumer keypair (source key). REPO= CONTEXT=
	@bash scripts/keys.sh rotate "$(REPO)" "$(CONTEXT)"

retire: ## Remove a consumer keypair no longer granted in access.map. REPO= CONTEXT=
	@bash scripts/keys.sh retire "$(REPO)" "$(CONTEXT)"

verify: ## Prove each consumer decrypts exactly its files, and dist/ is fresh (source key)
	@bash scripts/verify.sh

##@ Consumer

dist-decrypt-env: ## SOPS_AGE_KEY=... make dist-decrypt-env [FILE=oss.env] [KEY=NAME] [FORMAT=dotenv]
	@FILE="$(FILE)" KEY="$(KEY)" FORMAT="$(FORMAT)" bash ./dist-decrypt-env.sh dist

dist-decrypt: ## SOPS_AGE_KEY=... make dist-decrypt [FILE=ios/AuthKey_ABC123.p8]
	@FILE="$(FILE)" bash ./dist-decrypt.sh dist

##@ GitHub

gh-runs-list: ## List this repo's in-flight Actions runs (status != completed)
	@out=$$(gh run list --limit $(GH_LIMIT) \
	  --json status,workflowName,headBranch,event,url \
	  --jq '.[] | select(.status != "completed") | "  \(.status)\t\(.workflowName)\t\(.headBranch)\t\(.event)\t\(.url)"' 2>&1) \
	  || { printf '  \033[33m⚠\033[0m gh run list failed (auth? run `gh auth login`)\n'; exit 0; }; \
	if [ -z "$$out" ]; then printf '  \033[2mno active runs\033[0m\n'; \
	else printf '%s\n' "$$out" | column -t -s "$$(printf '\t')"; fi

gh-runs-watch: ## Watch this repo's in-flight Actions runs until each completes
	@ids=$$(gh run list --limit $(GH_LIMIT) --json status,databaseId \
	  --jq '.[] | select(.status != "completed") | .databaseId' 2>/dev/null); \
	if [ -z "$$ids" ]; then printf '  \033[2mno active runs\033[0m\n'; exit 0; fi; \
	for id in $$ids; do \
	  gh run watch "$$id" --compact || printf '  \033[33m⚠\033[0m watch failed for run %s\n' "$$id"; \
	done

gh-runs-status: ## Show pass/fail of the last completed run per workflow
	@out=$$(gh run list --limit $(GH_LIMIT) \
	  --json conclusion,workflowName,headBranch,url,status,updatedAt \
	  --jq '[.[] | select(.status == "completed")] | group_by(.workflowName) | map(sort_by(.updatedAt) | last) | sort_by(.updatedAt) | .[] | (now - (.updatedAt | fromdateiso8601)) as $$age | "\(.conclusion)\t\(.workflowName)\t\(.headBranch)\t\(.url)\t\($$age | floor)"' \
	  2>&1) \
	  || { printf '  \033[33m⚠\033[0m gh run list failed (auth? run `gh auth login`)\n'; exit 0; }; \
	if [ -z "$$out" ]; then printf '  \033[2mno completed runs\033[0m\n'; exit 0; fi; \
	esc=$$(printf '\033'); \
	printf '%s\n' "$$out" | while IFS=$$'\t' read -r conclusion name branch url age_secs; do \
	  if [ "$$conclusion" = "success" ]; then mark="ok"; \
	  elif [ "$$conclusion" = "skipped" ] || [ "$$conclusion" = "neutral" ]; then mark="skip"; \
	  else mark="fail"; fi; \
	  if [ "$$age_secs" -lt 60 ]; then age="$${age_secs}s"; \
	  elif [ "$$age_secs" -lt 3600 ]; then age="$$((age_secs / 60))m"; \
	  elif [ "$$age_secs" -lt 86400 ]; then age="$$((age_secs / 3600))h"; \
	  else age="$$((age_secs / 86400))d"; fi; \
	  printf '%s\t%s\t%s\t%s\t%s\n' "$$mark" "$$name" "$$branch" "$$age" "$$url"; \
	done | column -t -s "$$(printf '\t')" \
	| sed -e "s/^ok  /$${esc}[32m✓$${esc}[0m   /" \
	      -e "s/^skip/$${esc}[2m-$${esc}[0m   /" \
	      -e "s/^fail/$${esc}[31m✗$${esc}[0m   /" \
	      -e 's/^/  /'

##@ Release

bump: ## No-op: consumers always read dist/ at HEAD, so nothing is versioned

##@ Danger

set-keys: ## [danger] Push SOPS_AGE_KEY to GitHub for all (or REPO= / CONTEXT=) consumers
	$(call confirm,CONFIRM_SET_KEYS,this writes SOPS_AGE_KEY secrets to GitHub repos under $(OWNER))
	@OWNER="$(OWNER)" bash scripts/set-consumer-keys.sh "$(REPO)" "$(CONTEXT)"
