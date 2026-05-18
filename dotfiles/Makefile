# Dotfiles install targets.
#
# Most of the symlinks (fish, zshrc, exrc, profile, ...) are still installed by
# hand per the per-tool READMEs; this Makefile is the home for managed
# multi-file targets that benefit from a single command.

DOTFILES_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
GIT_CONFIG_DIR := $(HOME)/.config/git
GIT_FRAGMENTS := $(wildcard $(DOTFILES_DIR)/git/*.gitconfig)

.DEFAULT_GOAL := help
.PHONY: help link-git

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

link-git: ## Symlink dotfiles/git/*.gitconfig into ~/.config/git/ (idempotent).
	@mkdir -p $(GIT_CONFIG_DIR)
	@set -e; for src in $(GIT_FRAGMENTS); do \
		dst=$(GIT_CONFIG_DIR)/$$(basename $$src); \
		ln -snf $$src $$dst && echo "linked $$dst -> $$src"; \
	done
