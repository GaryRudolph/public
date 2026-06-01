# Dotfiles install targets.
#
# Most of the symlinks (fish, zshrc, exrc, profile, ...) are still installed by
# hand per the per-tool READMEs; this Makefile is the home for managed
# multi-file targets that benefit from a single command.

DOTFILES_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
GIT_CONFIG_DIR := $(HOME)/.config/git
GIT_FRAGMENTS := $(wildcard $(DOTFILES_DIR)/git/*.gitconfig)
GHOSTTY_CONFIG_DIR := $(HOME)/.config/ghostty

.DEFAULT_GOAL := help
.PHONY: help install link-git link-ghostty

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: link-git link-ghostty ## Install all managed dotfile symlinks.

link-git: ## Symlink dotfiles/git/*.gitconfig into ~/.config/git/ (idempotent).
	@mkdir -p $(GIT_CONFIG_DIR)
	@set -e; for src in $(GIT_FRAGMENTS); do \
		dst=$(GIT_CONFIG_DIR)/$$(basename $$src); \
		ln -snf $$src $$dst && echo "linked $$dst -> $$src"; \
	done

link-ghostty: ## Symlink dotfiles/ghostty/config into ~/.config/ghostty/ (backs up an existing file to config.bak).
	@mkdir -p $(GHOSTTY_CONFIG_DIR)
	@src=$(DOTFILES_DIR)/ghostty/config; dst=$(GHOSTTY_CONFIG_DIR)/config; \
	if [ -L "$$dst" ]; then \
		ln -snf $$src $$dst && echo "relinked $$dst -> $$src"; \
	elif [ -e "$$dst" ]; then \
		if [ -e "$$dst.bak" ]; then \
			echo "refusing to overwrite existing $$dst.bak; leaving $$dst untouched" >&2; exit 1; \
		fi; \
		mv $$dst $$dst.bak && echo "backed up $$dst -> $$dst.bak"; \
		ln -snf $$src $$dst && echo "linked $$dst -> $$src"; \
	else \
		ln -snf $$src $$dst && echo "linked $$dst -> $$src"; \
	fi
