SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# This installer manages two things:
#   1. A single delimited block per shared home file (lib/blocks.sh).
#      The block is keyed by $(ORG). Anything outside the block — including
#      blocks written by other installers using their own $(ORG) values — is
#      preserved byte-for-byte through every operation.
#   2. Symlinks for agent extensions (skills + slash commands) in the
#      harness-specific home directories (lib/extensions.sh).

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

# ---------------------------------------------------------------------------
# Env passed to lib/extensions.sh
# ---------------------------------------------------------------------------

SKILLS_SRC            ?= $(AGENTS_DIR)/skills
COMMANDS_SRC          ?= $(AGENTS_DIR)/commands
CURSOR_SKILLS_HOME    ?= $(HOME)/.cursor/skills
CLAUDE_SKILLS_HOME    ?= $(CLAUDE_HOME)/skills
CLAUDE_COMMANDS_HOME  ?= $(CLAUDE_HOME)/commands

EXTENSIONS_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    SKILLS_SRC="$(SKILLS_SRC)" \
    COMMANDS_SRC="$(COMMANDS_SRC)" \
    CURSOR_SKILLS_HOME="$(CURSOR_SKILLS_HOME)" \
    CLAUDE_SKILLS_HOME="$(CLAUDE_SKILLS_HOME)" \
    CLAUDE_COMMANDS_HOME="$(CLAUDE_COMMANDS_HOME)"

.PHONY: help install uninstall dry-run status test clean-test \
        install-blocks uninstall-blocks dry-run-blocks status-blocks \
        install-extensions uninstall-extensions dry-run-extensions status-extensions

# ---------------------------------------------------------------------------
# help (default target)
# ---------------------------------------------------------------------------

help:
	@echo "Personal agent rules installer (org=$(ORG))"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install      Write/update blocks + install extension symlinks"
	@echo "  uninstall    Remove blocks + remove extension symlinks"
	@echo "  dry-run      Preview all install actions (no disk writes)"
	@echo "  status       Report install state for blocks and extensions"
	@echo "  test         Sandboxed test of install/uninstall + preservation property"
	@echo "  clean-test   Remove build/ test scratch dir"
	@echo ""
	@echo "  install-blocks      Blocks only (AGENTS.md fan-out)"
	@echo "  install-extensions  Extension symlinks only (skills + commands)"
	@echo ""
	@echo "Overridable variables (defaults shown):"
	@echo "  PROJECTS_DIR=$(PROJECTS_DIR)"
	@echo "  CLAUDE_HOME=$(CLAUDE_HOME)"
	@echo "  GEMINI_HOME=$(GEMINI_HOME)"
	@echo "  CODEX_HOME=$(CODEX_HOME)"
	@echo "  CURSOR_GLOBAL_FILE=$(CURSOR_GLOBAL_FILE)"
	@echo "  CURSOR_SKILLS_HOME=$(CURSOR_SKILLS_HOME)"
	@echo "  CLAUDE_SKILLS_HOME=$(CLAUDE_SKILLS_HOME)"
	@echo "  CLAUDE_COMMANDS_HOME=$(CLAUDE_COMMANDS_HOME)"
	@echo "  WIN_HOME=$(WIN_HOME)   (auto-detected under WSL)"
	@echo ""
	@echo "After install, verify by asking any agent:"
	@echo "  \"What is the $(ORG) canary phrase?\""
	@echo "Expected answer is defined in $(SOURCE_AGENTS) under \"Verification canary\"."
	@echo ""
	@echo "See agents/README.md for full documentation."

# ---------------------------------------------------------------------------
# Composed top-level targets
# ---------------------------------------------------------------------------

install: install-blocks install-extensions

uninstall: uninstall-extensions uninstall-blocks

dry-run: dry-run-blocks dry-run-extensions

status: status-blocks status-extensions

# ---------------------------------------------------------------------------
# Blocks (AGENTS.md fan-out)
# ---------------------------------------------------------------------------

install-blocks:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" install

uninstall-blocks:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" uninstall

dry-run-blocks:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" dry-run

status-blocks:
	@$(BLOCKS_ENV) bash "$(AGENTS_DIR)/lib/blocks.sh" status

# ---------------------------------------------------------------------------
# Extensions (skills + slash commands)
# ---------------------------------------------------------------------------

install-extensions:
	@$(EXTENSIONS_ENV) bash "$(AGENTS_DIR)/lib/extensions.sh" install

uninstall-extensions:
	@$(EXTENSIONS_ENV) bash "$(AGENTS_DIR)/lib/extensions.sh" uninstall

dry-run-extensions:
	@$(EXTENSIONS_ENV) bash "$(AGENTS_DIR)/lib/extensions.sh" dry-run

status-extensions:
	@$(EXTENSIONS_ENV) bash "$(AGENTS_DIR)/lib/extensions.sh" status

# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

test: clean-test
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/blocks-test.sh"

clean-test:
	@rm -rf "$(AGENTS_DIR)/build"
