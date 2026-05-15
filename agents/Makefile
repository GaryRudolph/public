SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# This installer manages a single delimited block per shared home file. The
# block is keyed by $(ORG). Anything outside the block — including blocks
# written by other installers using their own $(ORG) values — is preserved
# byte-for-byte through every operation.

ORG               ?= personal
AGENTS_DIR        ?= $(CURDIR)
SOURCE_AGENTS     ?= $(AGENTS_DIR)/AGENTS.md
MAKEFILE_LABEL    ?= ~/Projects/personal/public/agents/Makefile

# ---------------------------------------------------------------------------
# Home-file targets
# ---------------------------------------------------------------------------

CLAUDE_HOME       ?= $(HOME)/.claude
GEMINI_HOME       ?= $(HOME)/.gemini
CODEX_HOME        ?= $(HOME)/.codex
CURSOR_GLOBAL_FILE ?= $(HOME)/AGENTS.md
XCODE_CLAUDE_DIR  ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig
XCODE_CODEX_DIR   ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/codex

# ---------------------------------------------------------------------------
# Legacy v1 cleanup
# ---------------------------------------------------------------------------
# Removes per-project artifacts written by the v1 fan-out installer that
# preceded this one. Runs unconditionally on both install and uninstall.

PROJECTS_DIR              ?= $(HOME)/Projects
LEGACY_GITIGNORE_CURSOR    := .cursor/rules/personal-*.mdc
LEGACY_CURSOR_GLOB         := personal-*.mdc

# WIN_HOME is auto-detected from /proc/version when running under WSL.
WIN_HOME ?=

# ---------------------------------------------------------------------------
# Env passed to lib/blocks.sh
# ---------------------------------------------------------------------------

BLOCKS_ENV = \
    ORG="$(ORG)" \
    SOURCE_AGENTS="$(SOURCE_AGENTS)" \
    MAKEFILE_LABEL="$(MAKEFILE_LABEL)" \
    CLAUDE_HOME="$(CLAUDE_HOME)" \
    GEMINI_HOME="$(GEMINI_HOME)" \
    CODEX_HOME="$(CODEX_HOME)" \
    CURSOR_GLOBAL_FILE="$(CURSOR_GLOBAL_FILE)" \
    XCODE_CLAUDE_DIR="$(XCODE_CLAUDE_DIR)" \
    XCODE_CODEX_DIR="$(XCODE_CODEX_DIR)" \
    PROJECTS_DIR="$(PROJECTS_DIR)" \
    LEGACY_GITIGNORE_CURSOR="$(LEGACY_GITIGNORE_CURSOR)" \
    LEGACY_CURSOR_GLOB="$(LEGACY_CURSOR_GLOB)" \
    WIN_HOME="$(WIN_HOME)"

TEST_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    LEGACY_GITIGNORE_CURSOR="$(LEGACY_GITIGNORE_CURSOR)" \
    LEGACY_CURSOR_GLOB="$(LEGACY_CURSOR_GLOB)"

.PHONY: help install uninstall dry-run status test clean-test

# ---------------------------------------------------------------------------
# help (default target)
# ---------------------------------------------------------------------------

help:
	@echo "Personal agent rules installer (org=$(ORG))"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install      Write/update the $(ORG) block in each home file (also runs v1 cleanup)"
	@echo "  uninstall    Remove the $(ORG) block from each home file (also runs v1 cleanup)"
	@echo "  dry-run      Preview install actions (no disk writes)"
	@echo "  status       Report install state for this installer only"
	@echo "  test         Sandboxed test of install/uninstall + preservation property"
	@echo "  clean-test   Remove build/ test scratch dir"
	@echo ""
	@echo "Overridable variables (defaults shown):"
	@echo "  PROJECTS_DIR=$(PROJECTS_DIR)"
	@echo "  CLAUDE_HOME=$(CLAUDE_HOME)"
	@echo "  GEMINI_HOME=$(GEMINI_HOME)"
	@echo "  CODEX_HOME=$(CODEX_HOME)"
	@echo "  CURSOR_GLOBAL_FILE=$(CURSOR_GLOBAL_FILE)"
	@echo "  WIN_HOME=$(WIN_HOME)   (auto-detected under WSL)"
	@echo ""
	@echo "After install, verify by asking any agent:"
	@echo "  \"What is the $(ORG) canary phrase?\""
	@echo "Expected answer is defined in $(SOURCE_AGENTS) under \"Verification canary\"."
	@echo ""
	@echo "See agents/README.md for full documentation."

# ---------------------------------------------------------------------------
# install / uninstall / dry-run / status
# ---------------------------------------------------------------------------

install:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" install

uninstall:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" uninstall

dry-run:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" dry-run

status:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" status

# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

test: clean-test
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/blocks-test.sh"

clean-test:
	@rm -rf "$(AGENTS_DIR)/build"
