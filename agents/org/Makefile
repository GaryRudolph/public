# Claude Code managed settings for the orgs in settings.json (README.md).
SHELL := /bin/bash
.DEFAULT_GOAL := help
ORG_DIR := $(CURDIR)
REPO_DIR := $(abspath $(ORG_DIR)/../..)

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

render: ## Regenerate claude-managed-settings.json from the allowlist and the base
	@bash "$(ORG_DIR)/render.sh" render

check: ## Fail when claude-managed-settings.json is stale
	@bash "$(ORG_DIR)/render.sh" check

test: check ## check, plus the issue script's tests
	@cd "$(REPO_DIR)" && python3 -m unittest discover -s agents/org/tests -q

.PHONY: help render check test
