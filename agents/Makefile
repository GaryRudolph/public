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
REPO_DIR          ?= $(abspath $(AGENTS_DIR)/..)
PLUGINS_DIR       ?= $(REPO_DIR)/plugins
# agents/AGENTS.md is a symlink to the core standards inside the plugin.
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

# Allowlists Windows-side destinations (derived in-script from WIN_HOME when
# empty; override to write to a non-standard location under the Windows home).
WIN_CURSOR_DATA_HOME ?=
WIN_CLAUDE_DATA_HOME ?=
WIN_GEMINI_DATA_HOME ?=

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
    WIN_HOME="$(WIN_HOME)" \
    CLAUDE_BLOCK="$(CLAUDE_BLOCK)" \
    CODEX_BLOCK="$(CODEX_BLOCK)" \
    GEMINI_BLOCK="$(GEMINI_BLOCK)"

TEST_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    LEGACY_GITIGNORE_CURSOR="$(LEGACY_GITIGNORE_CURSOR)" \
    LEGACY_CURSOR_GLOB="$(LEGACY_CURSOR_GLOB)"

# ---------------------------------------------------------------------------
# Allowlists pass — tool-agnostic meta-source → Cursor IDE/CLI + Claude Code
#                   + Gemini CLI Policy Engine
# ---------------------------------------------------------------------------

ALLOWLISTS_SRC    ?= $(AGENTS_DIR)/allowlists/personal.json
CURSOR_DATA_HOME  ?= $(HOME)/.cursor
CLAUDE_DATA_HOME  ?= $(HOME)/.claude
GEMINI_DATA_HOME  ?= $(GEMINI_HOME)

ALLOWLISTS_ENV = \
    ORG="$(ORG)" \
    ALLOWLISTS_SRC="$(ALLOWLISTS_SRC)" \
    CURSOR_DATA_HOME="$(CURSOR_DATA_HOME)" \
    CLAUDE_DATA_HOME="$(CLAUDE_DATA_HOME)" \
    GEMINI_DATA_HOME="$(GEMINI_DATA_HOME)" \
    WIN_HOME="$(WIN_HOME)" \
    WIN_CURSOR_DATA_HOME="$(WIN_CURSOR_DATA_HOME)" \
    WIN_CLAUDE_DATA_HOME="$(WIN_CLAUDE_DATA_HOME)" \
    WIN_GEMINI_DATA_HOME="$(WIN_GEMINI_DATA_HOME)" \
    MAKEFILE_LABEL="$(MAKEFILE_LABEL)"

# ---------------------------------------------------------------------------
# Env passed to lib/extensions.sh
# ---------------------------------------------------------------------------

# Skills live inside the plugins so one tree serves Claude (plugin sync) and
# every tool that scans a skills directory (symlinks below).
SKILLS_SRC                ?= $(PLUGINS_DIR)/personal/skills:$(PLUGINS_DIR)/workstation/skills
LEGACY_SKILLS_SRC         ?= $(AGENTS_DIR)/skills
COMMANDS_SRC              ?= $(AGENTS_DIR)/commands

# Tool modes (home | plugin) -------------------------------------------------
# home:   this installer writes the tool's home-file block and skill symlinks.
# plugin: the tool gets standards and skills from its `personal` plugin, so
#         install removes whatever this installer wrote for it before.
# Switch a tool to plugin only after its plugin is installed (agents/runbook.md).
# Put per-machine choices in agents/local.mk (gitignored), e.g. CODEX_MODE := plugin
-include $(AGENTS_DIR)/local.mk
CLAUDE_MODE               ?= plugin
CODEX_MODE                ?= home
GEMINI_MODE               ?= home
# Cursor's plugin carries skills only, so ~/AGENTS.md stays either way.
CURSOR_MODE               ?= home

$(foreach v,CLAUDE_MODE CODEX_MODE GEMINI_MODE CURSOR_MODE,\
  $(if $(filter home plugin,$($(v))),,$(error $(v) must be home or plugin, got '$($(v))')))

block_for  = $(if $(filter plugin,$(1)),remove,keep)
skills_for = $(if $(filter plugin,$(1)),plugin,symlink)

CLAUDE_BLOCK              := $(call block_for,$(CLAUDE_MODE))
CODEX_BLOCK               := $(call block_for,$(CODEX_MODE))
GEMINI_BLOCK              := $(call block_for,$(GEMINI_MODE))
CLAUDE_SKILLS_MODE        := $(call skills_for,$(CLAUDE_MODE))
CURSOR_SKILLS_MODE        := $(call skills_for,$(CURSOR_MODE))
# Codex and Gemini share ~/.agents/skills: keep it until both use plugins.
AGENTS_SKILLS_MODE        := $(if $(and $(filter plugin,$(CODEX_MODE)),$(filter plugin,$(GEMINI_MODE))),plugin,symlink)

# Unix-side destinations (symlinks).
CURSOR_SKILLS_HOME        ?= $(HOME)/.cursor/skills
AGENTS_SKILLS_HOME        ?= $(HOME)/.agents/skills
CLAUDE_SKILLS_HOME        ?= $(CLAUDE_HOME)/skills
CLAUDE_COMMANDS_HOME      ?= $(CLAUDE_HOME)/commands

# Windows-side destinations (copies, under $(WIN_HOME)). Left empty when
# WIN_HOME is empty; extensions.sh fills them in once WIN_HOME is resolved
# (either explicitly or via WSL auto-detection).
WIN_CURSOR_SKILLS_HOME    ?=
WIN_AGENTS_SKILLS_HOME    ?=
WIN_CLAUDE_SKILLS_HOME    ?=
WIN_CLAUDE_COMMANDS_HOME  ?=

EXTENSIONS_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    SKILLS_SRC="$(SKILLS_SRC)" \
    LEGACY_SKILLS_SRC="$(LEGACY_SKILLS_SRC)" \
    COMMANDS_SRC="$(COMMANDS_SRC)" \
    CLAUDE_SKILLS_MODE="$(CLAUDE_SKILLS_MODE)" \
    CURSOR_SKILLS_MODE="$(CURSOR_SKILLS_MODE)" \
    AGENTS_SKILLS_MODE="$(AGENTS_SKILLS_MODE)" \
    CURSOR_SKILLS_HOME="$(CURSOR_SKILLS_HOME)" \
    AGENTS_SKILLS_HOME="$(AGENTS_SKILLS_HOME)" \
    CLAUDE_SKILLS_HOME="$(CLAUDE_SKILLS_HOME)" \
    CLAUDE_COMMANDS_HOME="$(CLAUDE_COMMANDS_HOME)" \
    WIN_HOME="$(WIN_HOME)" \
    WIN_CURSOR_SKILLS_HOME="$(WIN_CURSOR_SKILLS_HOME)" \
    WIN_AGENTS_SKILLS_HOME="$(WIN_AGENTS_SKILLS_HOME)" \
    WIN_CLAUDE_SKILLS_HOME="$(WIN_CLAUDE_SKILLS_HOME)" \
    WIN_CLAUDE_COMMANDS_HOME="$(WIN_CLAUDE_COMMANDS_HOME)"

.PHONY: help install uninstall dry-run status test test-blocks test-extensions test-allowlists clean-test \
        install-blocks uninstall-blocks dry-run-blocks status-blocks \
        install-extensions uninstall-extensions dry-run-extensions status-extensions \
        install-allowlists uninstall-allowlists dry-run-allowlists status-allowlists test-manifests test-secrets test-release status-modes \
        diff-allowlists restore-allowlists clean-allowlists \
        validate package

# ---------------------------------------------------------------------------
# help (default target)
# ---------------------------------------------------------------------------

help:
	@echo "Personal agent rules installer (org=$(ORG))"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install      Write/update blocks + install extension symlinks + render allowlists"
	@echo "  uninstall    Remove blocks + remove extension symlinks + remove allowlist sidecars"
	@echo "  dry-run      Preview all install actions (no disk writes)"
	@echo "  status       Report install state for blocks, extensions, and allowlists"
	@echo "  test         Sandboxed test of install/uninstall + preservation property"
	@echo "  clean-test   Remove build/ test scratch dir"
	@echo ""
	@echo "  install-blocks      Blocks only (AGENTS.md fan-out)"
	@echo "  install-extensions  Extension symlinks only (skills + commands)"
	@echo "  install-allowlists  Render allowlists into ~/.cursor/permissions.json,"
	@echo "                      ~/.cursor/cli-config.json, ~/.claude/settings.json,"
	@echo "                      and ~/.gemini/policies/$(ORG)-managed.toml"
	@echo ""
	@echo "  validate     Validate the Claude marketplace and plugins (needs claude CLI)"
	@echo "               and check the Codex/Cursor/Gemini manifests agree with them"
	@echo "  package      Zip each plugin into build/plugins/ for Customize > Upload plugin"
	@echo ""
	@echo "  diff-allowlists           Show expected vs actual for each rendered target"
	@echo "  restore-allowlists N=<n>  Restore .history/<file>.<n> back into place"
	@echo "  clean-allowlists          Remove .history/ backup dirs (explicit nuke knob)"
	@echo ""
	@echo "Overridable variables (defaults shown):"
	@echo "  PROJECTS_DIR=$(PROJECTS_DIR)"
	@echo "  CLAUDE_HOME=$(CLAUDE_HOME)"
	@echo "  GEMINI_HOME=$(GEMINI_HOME)"
	@echo "  CODEX_HOME=$(CODEX_HOME)"
	@echo "  CURSOR_GLOBAL_FILE=$(CURSOR_GLOBAL_FILE)"
	@echo "  CURSOR_SKILLS_HOME=$(CURSOR_SKILLS_HOME)"
	@echo "  AGENTS_SKILLS_HOME=$(AGENTS_SKILLS_HOME)   (Codex, Gemini CLI)"
	@echo "  CLAUDE_MODE=$(CLAUDE_MODE)   CODEX_MODE=$(CODEX_MODE)   GEMINI_MODE=$(GEMINI_MODE)   CURSOR_MODE=$(CURSOR_MODE)"
	@echo "               (home | plugin; plugin removes what this installer wrote for that tool)"
	@echo "  CLAUDE_SKILLS_HOME=$(CLAUDE_SKILLS_HOME)"
	@echo "  CLAUDE_COMMANDS_HOME=$(CLAUDE_COMMANDS_HOME)"
	@echo "  WIN_HOME=$(WIN_HOME)   (auto-detected under WSL; triggers Windows-side copies)"
	@echo ""
	@echo "After install, verify by asking any agent:"
	@echo "  \"What is the $(ORG) canary phrase?\""
	@echo "Expected answer is defined in $(SOURCE_AGENTS) under \"Verification canary\"."
	@echo ""
	@echo "See agents/README.md for full documentation."

# ---------------------------------------------------------------------------
# Composed top-level targets
# ---------------------------------------------------------------------------

install: install-blocks install-extensions install-allowlists

uninstall: uninstall-allowlists uninstall-extensions uninstall-blocks
	@echo ""
	@echo "Plugins aren't managed by this Makefile. To remove them too:"
	@echo "  Claude:  Customize > Plugins in claude.ai, and on this Mac"
	@echo "           claude plugin uninstall personal@personal; claude plugin marketplace remove personal"
	@echo "  Codex:   codex plugin marketplace remove personal (and uninstall in /plugins)"
	@echo "  Cursor:  Customize > Plugins > personal > Uninstall"
	@echo "  Gemini:  gemini extensions uninstall personal"

dry-run: dry-run-blocks dry-run-extensions dry-run-allowlists

status: status-modes status-blocks status-extensions status-allowlists

status-modes:
	@echo "modes: CLAUDE_MODE=$(CLAUDE_MODE) CODEX_MODE=$(CODEX_MODE) GEMINI_MODE=$(GEMINI_MODE) CURSOR_MODE=$(CURSOR_MODE)"
	@echo ""

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

test: test-blocks test-extensions test-allowlists test-manifests test-secrets test-release

test-blocks: clean-test
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/blocks-test.sh"

test-extensions:
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/extensions-test.sh"

test-allowlists:
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/allowlists-test.sh"

test-manifests:
	@python3 "$(AGENTS_DIR)/lib/manifests-check.py"

# Needs sops and age; prints SKIP and passes when they're missing.
test-secrets:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-secrets/tests/test-kit.sh"

test-release:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-release/tests/test-release.sh"

clean-test:
	@rm -rf "$(AGENTS_DIR)/build"

# ---------------------------------------------------------------------------
# Allowlists (permissions.json + cli-config.json + settings.json)
# ---------------------------------------------------------------------------

install-allowlists:
	@$(ALLOWLISTS_ENV) bash "$(AGENTS_DIR)/lib/allowlists.sh" install

uninstall-allowlists:
	@$(ALLOWLISTS_ENV) REMOVE_HISTORY="$(REMOVE_HISTORY)" bash "$(AGENTS_DIR)/lib/allowlists.sh" uninstall

dry-run-allowlists:
	@$(ALLOWLISTS_ENV) bash "$(AGENTS_DIR)/lib/allowlists.sh" dry-run

status-allowlists:
	@$(ALLOWLISTS_ENV) bash "$(AGENTS_DIR)/lib/allowlists.sh" status

diff-allowlists:
	@$(ALLOWLISTS_ENV) bash "$(AGENTS_DIR)/lib/allowlists.sh" diff

restore-allowlists:
	@$(ALLOWLISTS_ENV) RESTORE_N="$(N)" bash "$(AGENTS_DIR)/lib/allowlists.sh" restore

clean-allowlists:
	@$(ALLOWLISTS_ENV) bash "$(AGENTS_DIR)/lib/allowlists.sh" clean

# ---------------------------------------------------------------------------
# Plugins (marketplace at the repo root, plugins under plugins/)
# ---------------------------------------------------------------------------

PLUGINS      ?= personal workstation
PACKAGE_DIR  ?= $(AGENTS_DIR)/build/plugins

validate: test-manifests
	@command -v claude >/dev/null || { echo "claude CLI not found"; exit 1; }
	@claude plugin validate "$(REPO_DIR)"
	@for p in $(PLUGINS); do claude plugin validate "$(PLUGINS_DIR)/$$p" || exit 1; done

package:
	@mkdir -p "$(PACKAGE_DIR)"
	@for p in $(PLUGINS); do \
		rm -f "$(PACKAGE_DIR)/$$p.zip"; \
		(cd "$(PLUGINS_DIR)/$$p" && zip -qr "$(PACKAGE_DIR)/$$p.zip" . -x '*/__pycache__/*' '*.pyc' '.DS_Store'); \
		echo "packaged $(PACKAGE_DIR)/$$p.zip"; \
	done
