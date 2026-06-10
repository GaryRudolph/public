# {{REPO_NAME}} Makefile
#
# Single source of truth for build / test / lint / format commands.
# Humans, agents, and CI run the same verbs — CI calls `make <target>`.
#
# Conventions:
#   - `.DEFAULT_GOAL := help`; bare `make` prints grouped targets.
#   - Self-documenting: `## comment` after a target; `##@ Section` for headers.
#   - Verb names follow the standard set (format, not fmt).
#   - Remote-mutating targets under `##@ Danger` with CONFIRM_* guards.
#
# See Makefile.md for the narrative reference.

SHELL := bash

.DEFAULT_GOAL := help

.PHONY: help init build lint format test ci pre-commit doctor clean \
        gh-runs-list gh-runs-watch gh-runs-status bump deploy

MODE ?= default
GH_LIMIT ?= 50
LEVEL ?= patch

confirm = @if [ -z "$($(1))" ]; then \
  printf 'Refusing to run "make %s": %s\nRe-run with %s=1.\n' "$@" "$(2)" "$(1)"; \
  exit 1; \
fi

##@ Develop

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0,5)}' $(MAKEFILE_LIST)

init: ## {{INIT_DESCRIPTION}}
	{{INIT_RECIPE}}

build: ## {{BUILD_DESCRIPTION}}
	{{BUILD_RECIPE}}

lint: ## {{LINT_DESCRIPTION}}
	{{LINT_RECIPE}}

format: ## {{FORMAT_DESCRIPTION}}
	{{FORMAT_RECIPE}}

test: ## {{TEST_DESCRIPTION}}
	{{TEST_RECIPE}}

ci: {{CI_PREREQS}} ## Run the full pre-push gate (what CI runs)

pre-commit: ci ## Run the local gate before committing or pushing (alias of ci)

doctor: ## Check required tools for this repo (read-only). MODE=default|release
	@command -v triage >/dev/null 2>&1 || { printf 'triage not found - install: brew install lolay/tap/triage\n' >&2; exit 1; }
	@triage --profile $(MODE)

clean: ## {{CLEAN_DESCRIPTION}}
	{{CLEAN_RECIPE}}

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

bump: ## Bump version (LEVEL=patch|minor|major); prints the new version
	{{BUMP_RECIPE}}

##@ Danger

deploy: build ## [danger] {{DEPLOY_DESCRIPTION}}
	$(call confirm,CONFIRM_DEPLOY,{{DEPLOY_CONFIRM_TEXT}})
	{{DEPLOY_RECIPE}}
