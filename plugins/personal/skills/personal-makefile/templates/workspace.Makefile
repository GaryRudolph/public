# {{ESTATE_TITLE}} Makefile
#
# Thin orchestration wrapper for the {{ESTATE_NAME}} multi-repo estate. This file
# clones, initialises, builds, and runs gates across the child repos — it
# does not own any build logic itself. Child repo Makefiles are the source
# of truth for their own commands.
#
# Conventions (shared across every {{ESTATE_NAME}}-* repo):
#   - `.DEFAULT_GOAL := help`; bare `make` prints the grouped target list.
#   - Self-documenting: a `## comment` after a target shows up in `make help`;
#     a `##@ Section` line renders as a header.
#   - Recipes run under bash (SHELL below).
#
# The workspace is optional. Every child repo is fully usable on its own.
# See README.md and AGENTS.md for delegation protocol.

SHELL := bash

.DEFAULT_GOAL := help

include repos.mk

_REPO_SPECS := $(foreach r,$(REPOS),$r:$(REPO_URL.$r):$(REPO_BRANCH.$r))

.PHONY: help init doctor build ci pre-commit clean \
        git-fetch git-pull git-push git-status \
        gh-runs-list gh-runs-watch gh-runs-status

MODE ?= default
GH_LIMIT ?= 50

##@ Develop

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0,5)}' $(MAKEFILE_LIST)

init: ## Clone missing repos, run per-repo `make init`, then check environment
	@set -euo pipefail; \
	echo ""; \
	printf '\033[1m==> Checking repo checkouts\033[0m\n'; \
	for spec in $(_REPO_SPECS); do \
	  dir="$${spec%%:*}"; \
	  rest="$${spec#*:}"; \
	  url="$${rest%:*}"; \
	  branch="$${rest##*:}"; \
	  if [ -d "$$dir/.git" ]; then \
	    actual=$$(git -C "$$dir" remote get-url origin 2>/dev/null || echo ""); \
	    if [ "$$actual" = "$$url" ]; then \
	      printf '  \033[32m✓\033[0m %-22s already present\n' "$$dir"; \
	    else \
	      printf '  \033[33m⚠\033[0m %-22s present but origin mismatch\n    expected: %s\n    found:    %s\n    Skipping clone.\n' "$$dir" "$$url" "$$actual" >&2; \
	    fi; \
	  elif [ -e "$$dir" ]; then \
	    printf '  \033[33m⚠\033[0m %-22s exists but is not a git repo — remove it to allow clone\n' "$$dir" >&2; \
	  else \
	    printf '  \033[34m→\033[0m %-22s cloning from %s ...\n' "$$dir" "$$url"; \
	    git clone --branch "$$branch" "$$url" "$$dir"; \
	    printf '  \033[32m✓\033[0m %-22s cloned\n' "$$dir"; \
	  fi; \
	done; \
	echo ""; \
	printf '\033[1m==> Running per-repo make init\033[0m\n'; \
	{{INIT_SKIP_NOTES}} \
	echo ""; \
	for r in $(REPOS_MAKE_INIT); do \
	  if [ -d "$$r" ]; then \
	    printf '  → %s\n' "$$r"; \
	    $(MAKE) -C "$$r" init; \
	    echo ""; \
	  else \
	    printf '  \033[33m⚠\033[0m %s not checked out; skipping make init\n' "$$r" >&2; \
	  fi; \
	done; \
	$(MAKE) doctor

doctor: ## Repo roster check + triage delegate tree. MODE=default|release
	@exit_code=0; \
	echo ""; \
	printf '\033[1m==> Repo roster\033[0m\n'; \
	for spec in $(_REPO_SPECS); do \
	  dir="$${spec%%:*}"; \
	  rest="$${spec#*:}"; \
	  url="$${rest%:*}"; \
	  tag=""; \
	  for fo in $(REPOS_FOLLOW_ONLY); do \
	    [ "$$fo" = "$$dir" ] && tag=" [follow-only]"; \
	  done; \
	  if [ -d "$$dir/.git" ]; then \
	    actual=$$(git -C "$$dir" remote get-url origin 2>/dev/null || echo ""); \
	    if [ "$$actual" = "$$url" ]; then \
	      printf '  \033[32m✓\033[0m %-22s present%s\n' "$$dir" "$$tag"; \
	    else \
	      printf '  \033[33m⚠\033[0m %-22s present but origin mismatch%s\n' "$$dir" "$$tag"; \
	      printf '                         expected: %s\n' "$$url"; \
	      printf '                         found:    %s\n' "$$actual"; \
	      exit_code=1; \
	    fi; \
	  else \
	    printf '  \033[31m✗\033[0m %-22s missing — run `make init` to clone%s\n' "$$dir" "$$tag"; \
	    exit_code=1; \
	  fi; \
	done; \
	echo ""; \
	if [ -f triage.yaml ]; then \
	  if ! command -v triage >/dev/null 2>&1; then \
	    printf 'triage not found - install: brew install lolay/tap/triage\n' >&2; \
	    exit 1; \
	  fi; \
	  printf '\033[1m==> Tool checks (triage --profile $(MODE))\033[0m\n'; \
	  if ! triage --profile $(MODE); then exit_code=1; fi; \
	else \
	  printf '\033[1m==> Delegating make doctor to each child repo (MODE=$(MODE))\033[0m\n'; \
	  for r in $(REPOS_MAKE_CI); do \
	    if [ -d "$$r" ]; then \
	      echo ""; printf '  → %s\n' "$$r"; \
	      if ! $(MAKE) -C "$$r" doctor MODE=$(MODE); then exit_code=1; fi; \
	    else \
	      printf '  \033[33m⚠\033[0m %s not checked out; skipping\n' "$$r" >&2; \
	    fi; \
	  done; \
	fi; \
	echo ""; \
	exit $$exit_code

build: ## Build all repos in dependency order
	@set -euo pipefail; \
	echo ""; \
	printf '\033[1m==> make build (dependency order)\033[0m\n'; \
	for r in $(REPOS_BUILD_ORDER); do \
	  if [ -d "$$r" ]; then \
	    echo ""; printf '  → %s\n' "$$r"; \
	    $(MAKE) -C "$$r" build; \
	  else \
	    printf '  \033[33m⚠\033[0m %s not checked out; skipping\n' "$$r" >&2; \
	  fi; \
	done; \
	echo ""

ci: ## Run `make ci` in each repo (dumb pass-through; each repo defines its own gate)
	@exit_code=0; \
	echo ""; \
	printf '\033[1m==> make ci (pass-through to each repo)\033[0m\n'; \
	for r in $(REPOS_MAKE_CI); do \
	  if [ -d "$$r" ]; then \
	    echo ""; printf '  → %s\n' "$$r"; \
	    if ! $(MAKE) -C "$$r" ci; then \
	      exit_code=1; \
	      printf '  \033[31m✗\033[0m %s: make ci failed\n' "$$r" >&2; \
	    fi; \
	  else \
	    printf '  \033[33m⚠\033[0m %s not checked out; skipping\n' "$$r" >&2; \
	  fi; \
	done; \
	echo ""; \
	exit $$exit_code

pre-commit: ## Run `make pre-commit` in each repo (dumb pass-through)
	@exit_code=0; \
	echo ""; \
	printf '\033[1m==> make pre-commit (pass-through to each repo)\033[0m\n'; \
	for r in $(REPOS_MAKE_CI); do \
	  if [ -d "$$r" ]; then \
	    echo ""; printf '  → %s\n' "$$r"; \
	    if ! $(MAKE) -C "$$r" pre-commit; then \
	      exit_code=1; \
	      printf '  \033[31m✗\033[0m %s: make pre-commit failed\n' "$$r" >&2; \
	    fi; \
	  else \
	    printf '  \033[33m⚠\033[0m %s not checked out; skipping\n' "$$r" >&2; \
	  fi; \
	done; \
	echo ""; \
	exit $$exit_code

clean: ## Run `make clean` in repos that define the target
	@set -euo pipefail; \
	echo ""; \
	printf '\033[1m==> make clean\033[0m\n'; \
	for r in $(REPOS_MAKE_CLEAN); do \
	  if [ -d "$$r" ]; then \
	    printf '  → %s\n' "$$r"; \
	    $(MAKE) -C "$$r" clean; \
	  else \
	    printf '  \033[33m⚠\033[0m %s not checked out; skipping\n' "$$r" >&2; \
	  fi; \
	done; \
	echo ""

##@ Git

git-status: ## git status -s across the workspace and all checked-out repos
	@echo ""; \
	printf '\033[1m==> workspace\033[0m\n'; \
	git status -s; \
	for r in $(REPOS); do \
	  if [ -d "$$r/.git" ]; then \
	    echo ""; printf '\033[1m==> %s\033[0m\n' "$$r"; \
	    git -C "$$r" status -s; \
	  fi; \
	done; \
	echo ""

git-fetch: ## git fetch --all --prune across the workspace and all checked-out repos
	@echo ""; \
	printf '\033[1m==> workspace\033[0m\n'; \
	git fetch --all --prune; \
	for r in $(REPOS); do \
	  if [ -d "$$r/.git" ]; then \
	    echo ""; printf '\033[1m==> %s\033[0m\n' "$$r"; \
	    git -C "$$r" fetch --all --prune; \
	  fi; \
	done; \
	echo ""

git-push: ## git push across workspace and repos (skips follow-only and on failure)
	@echo ""; \
	printf '\033[1m==> workspace\033[0m\n'; \
	git push 2>&1 || printf '  \033[33m⚠\033[0m workspace: push failed — skipping\n'; \
	for r in $(REPOS); do \
	  if [ -d "$$r/.git" ]; then \
	    follow_only=0; \
	    for fo in $(REPOS_FOLLOW_ONLY); do \
	      [ "$$fo" = "$$r" ] && follow_only=1; \
	    done; \
	    echo ""; printf '\033[1m==> %s\033[0m\n' "$$r"; \
	    if [ $$follow_only -eq 1 ]; then \
	      printf '  \033[33m⚠\033[0m follow-only mirror — skipping\n'; \
	    else \
	      git -C "$$r" push 2>&1 || \
	        printf '  \033[33m⚠\033[0m push failed — skipping\n'; \
	    fi; \
	  fi; \
	done; \
	echo ""

git-pull: ## git pull --ff-only across workspace and repos (skips dirty or diverged)
	@echo ""; \
	printf '\033[1m==> workspace\033[0m\n'; \
	git pull --ff-only 2>&1 || printf '  \033[33m⚠\033[0m workspace: cannot fast-forward — skipping\n'; \
	for r in $(REPOS); do \
	  if [ -d "$$r/.git" ]; then \
	    echo ""; printf '\033[1m==> %s\033[0m\n' "$$r"; \
	    if ! git -C "$$r" diff --quiet 2>/dev/null || ! git -C "$$r" diff --cached --quiet 2>/dev/null; then \
	      printf '  \033[33m⚠\033[0m dirty working tree — skipping pull\n'; \
	    else \
	      git -C "$$r" pull --ff-only 2>&1 || \
	        printf '  \033[33m⚠\033[0m cannot fast-forward — skipping\n'; \
	    fi; \
	  fi; \
	done; \
	echo ""

##@ GitHub

gh-runs-list: ## List in-flight Actions runs across all repos (delegates to each repo)
	@echo ""; \
	for r in $(REPOS_GH); do \
	  [ -d "$$r/.git" ] || continue; \
	  printf '\033[1m==> %s\033[0m\n' "$$r"; \
	  $(MAKE) --no-print-directory -C "$$r" gh-runs-list GH_LIMIT=$(GH_LIMIT) || true; \
	  echo ""; \
	done

gh-runs-watch: ## Watch in-flight Actions runs across all repos (delegates to each repo)
	@echo ""; \
	for r in $(REPOS_GH); do \
	  [ -d "$$r/.git" ] || continue; \
	  printf '\033[1m==> %s\033[0m\n' "$$r"; \
	  $(MAKE) --no-print-directory -C "$$r" gh-runs-watch GH_LIMIT=$(GH_LIMIT) || true; \
	  echo ""; \
	done

gh-runs-status: ## Show pass/fail of the last completed run per workflow across all repos
	@echo ""; \
	for r in $(REPOS_GH); do \
	  [ -d "$$r/.git" ] || continue; \
	  printf '\033[1m==> %s\033[0m\n' "$$r"; \
	  $(MAKE) --no-print-directory -C "$$r" gh-runs-status GH_LIMIT=$(GH_LIMIT) || true; \
	  echo ""; \
	done
