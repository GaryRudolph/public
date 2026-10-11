SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# Standards and skills ship as the personal plugins in ../plugins/ (Claude,
# Codex, Cursor, Gemini, Copilot CLI). This installer covers what plugins
# can't, on this machine:
#   1. A delimited block per shared home file (lib/blocks.sh), for tools in
#      home mode and for Xcode. Claude and Gemini get an @-import of
#      agents/AGENTS.md; Cursor and Codex get it inlined.
#   2. Skill links or copies in each tool's skills dir (lib/extensions.sh),
#      for tools in home mode. Cursor gets copies (it doesn't follow
#      symlinks for home-dir skills); the rest get symlinks.
#   3. Cursor user hooks (lib/hooks.sh): the denylist hook, and a refresh
#      hook for copy-mode skills.
#   4. Allowlists (lib/allowlists.sh): plugins can't ship permission rules.
#   5. Optionally, this checkout as a local Claude marketplace for live
#      edits (lib/local-marketplace.sh).

ORG               ?= personal
AGENTS_DIR        ?= $(CURDIR)
REPO_DIR          ?= $(abspath $(AGENTS_DIR)/..)
PLUGINS_DIR       ?= $(REPO_DIR)/plugins
# agents/AGENTS.md is a symlink to the core standards inside the plugin.
SOURCE_AGENTS     ?= $(AGENTS_DIR)/AGENTS.md
MAKEFILE_LABEL    ?= ~/Projects/personal/public/agents/Makefile

# ---------------------------------------------------------------------------
# Tool modes (home | plugin)
# ---------------------------------------------------------------------------
# home:   this installer writes the tool's block and skill links or copies.
# plugin: the tool gets standards and skills from the personal plugin, so
#         install removes whatever this installer wrote for it before.
# Switch a tool to plugin only after its plugin is installed (agents/runbook.md).
# Put per-machine choices in agents/local.mk (gitignored), e.g. CURSOR_MODE := plugin

-include $(AGENTS_DIR)/local.mk
CLAUDE_MODE       ?= plugin
CODEX_MODE        ?= home
GEMINI_MODE       ?= home
CURSOR_MODE       ?= home

$(foreach v,CLAUDE_MODE CODEX_MODE GEMINI_MODE CURSOR_MODE,\
  $(if $(filter home plugin,$($(v))),,$(error $(v) must be home or plugin, got '$($(v))')))

block_for          = $(if $(filter plugin,$(1)),remove,keep)
CLAUDE_BLOCK       := $(call block_for,$(CLAUDE_MODE))
CODEX_BLOCK        := $(call block_for,$(CODEX_MODE))
GEMINI_BLOCK       := $(call block_for,$(GEMINI_MODE))
# Cursor's plugin carries the core as the personal-core rule, so plugin mode
# drops ~/AGENTS.md too.
CURSOR_BLOCK       := $(call block_for,$(CURSOR_MODE))
CLAUDE_SKILLS_MODE := $(if $(filter plugin,$(CLAUDE_MODE)),plugin,symlink)
CURSOR_SKILLS_MODE := $(if $(filter plugin,$(CURSOR_MODE)),plugin,copy)
# Codex and Gemini share ~/.agents/skills: keep it until both use plugins.
AGENTS_SKILLS_MODE := $(if $(and $(filter plugin,$(CODEX_MODE)),$(filter plugin,$(GEMINI_MODE))),plugin,symlink)

# ---------------------------------------------------------------------------
# Home-file targets (blocks pass)
# ---------------------------------------------------------------------------

CLAUDE_HOME       ?= $(HOME)/.claude
GEMINI_HOME       ?= $(HOME)/.gemini
CODEX_HOME        ?= $(HOME)/.codex
CURSOR_GLOBAL_FILE ?= $(HOME)/AGENTS.md
XCODE_CLAUDE_DIR  ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig
XCODE_CODEX_DIR   ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/codex

# Cursor-only rules whose bodies ride in the Cursor block in home mode.
CURSOR_EXTRA_SOURCES ?=

# ---------------------------------------------------------------------------
# Legacy v1 cleanup
# ---------------------------------------------------------------------------
# Removes per-project Cursor / JetBrains symlinks and .gitignore entries that
# the v1 fan-out installer wrote into repos under $(PROJECTS_DIR).
# Idempotent; runs on every install and uninstall. Nothing else touches
# sibling repos.

PROJECTS_DIR              ?= $(HOME)/Projects
LEGACY_GITIGNORE_CURSOR    := .cursor/rules/personal-*.mdc
LEGACY_GITIGNORE_JETBRAINS :=
LEGACY_CURSOR_GLOB         := personal-*.mdc
LEGACY_JETBRAINS_GLOB      :=

# WIN_HOME is auto-detected from /proc/version when running under WSL.
# Override (or set explicitly on non-WSL Linux) by passing WIN_HOME=/some/path.
# Shared between the blocks, extensions, and allowlists passes.
WIN_HOME ?=

# Allowlists Windows-side destinations (derived in-script from WIN_HOME when
# empty; override to write to a non-standard location under the Windows home).
WIN_CURSOR_DATA_HOME ?=
WIN_CLAUDE_DATA_HOME ?=
WIN_GEMINI_DATA_HOME ?=

# ---------------------------------------------------------------------------
# Extensions pass — sources + per-harness destinations
# ---------------------------------------------------------------------------

# Skills live inside the plugins so one tree serves the plugin route and the
# home-dir route below.
SKILLS_SRC          ?= $(PLUGINS_DIR)/personal/skills:$(PLUGINS_DIR)/workstation/skills
CURSOR_SKILLS_SRC   ?=
COMMANDS_SRC        ?= $(AGENTS_DIR)/commands
LEGACY_SKILLS_SRC   ?= $(AGENTS_DIR)/skills
LEGACY_COMMANDS_SRC ?=

# Unix-side destinations. ~/.agents/skills serves Codex, Gemini, and Copilot
# CLI; the old per-tool ~/.gemini/skills and ~/.codex/skills are swept.
CURSOR_SKILLS_HOME        ?= $(HOME)/.cursor/skills
AGENTS_SKILLS_HOME        ?= $(HOME)/.agents/skills
CLAUDE_SKILLS_HOME        ?= $(CLAUDE_HOME)/skills
CLAUDE_COMMANDS_HOME      ?= $(CLAUDE_HOME)/commands
LEGACY_SKILLS_HOMES       ?= $(GEMINI_HOME)/skills:$(CODEX_HOME)/skills

# Windows-side destinations (copies, under $(WIN_HOME)). Left empty when
# WIN_HOME is empty; extensions.sh fills them in once WIN_HOME is resolved.
WIN_CURSOR_SKILLS_HOME    ?=
WIN_AGENTS_SKILLS_HOME    ?=
WIN_CLAUDE_SKILLS_HOME    ?=
WIN_CLAUDE_COMMANDS_HOME  ?=

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
    CLAUDE_BLOCK="$(CLAUDE_BLOCK)" \
    CODEX_BLOCK="$(CODEX_BLOCK)" \
    GEMINI_BLOCK="$(GEMINI_BLOCK)" \
    CURSOR_BLOCK="$(CURSOR_BLOCK)" \
    CURSOR_EXTRA_SOURCES="$(CURSOR_EXTRA_SOURCES)" \
    PROJECTS_DIR="$(PROJECTS_DIR)" \
    LEGACY_GITIGNORE_CURSOR="$(LEGACY_GITIGNORE_CURSOR)" \
    LEGACY_GITIGNORE_JETBRAINS="$(LEGACY_GITIGNORE_JETBRAINS)" \
    LEGACY_CURSOR_GLOB="$(LEGACY_CURSOR_GLOB)" \
    LEGACY_JETBRAINS_GLOB="$(LEGACY_JETBRAINS_GLOB)" \
    WIN_HOME="$(WIN_HOME)"

# ---------------------------------------------------------------------------
# Env passed to lib/extensions.sh
# ---------------------------------------------------------------------------

EXTENSIONS_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    SKILLS_SRC="$(SKILLS_SRC)" \
    CURSOR_SKILLS_SRC="$(CURSOR_SKILLS_SRC)" \
    COMMANDS_SRC="$(COMMANDS_SRC)" \
    LEGACY_SKILLS_SRC="$(LEGACY_SKILLS_SRC)" \
    LEGACY_COMMANDS_SRC="$(LEGACY_COMMANDS_SRC)" \
    CURSOR_SKILLS_MODE="$(CURSOR_SKILLS_MODE)" \
    AGENTS_SKILLS_MODE="$(AGENTS_SKILLS_MODE)" \
    CLAUDE_SKILLS_MODE="$(CLAUDE_SKILLS_MODE)" \
    CURSOR_SKILLS_HOME="$(CURSOR_SKILLS_HOME)" \
    AGENTS_SKILLS_HOME="$(AGENTS_SKILLS_HOME)" \
    CLAUDE_SKILLS_HOME="$(CLAUDE_SKILLS_HOME)" \
    CLAUDE_COMMANDS_HOME="$(CLAUDE_COMMANDS_HOME)" \
    LEGACY_SKILLS_HOMES="$(LEGACY_SKILLS_HOMES)" \
    WIN_HOME="$(WIN_HOME)" \
    WIN_CURSOR_SKILLS_HOME="$(WIN_CURSOR_SKILLS_HOME)" \
    WIN_AGENTS_SKILLS_HOME="$(WIN_AGENTS_SKILLS_HOME)" \
    WIN_CLAUDE_SKILLS_HOME="$(WIN_CLAUDE_SKILLS_HOME)" \
    WIN_CLAUDE_COMMANDS_HOME="$(WIN_CLAUDE_COMMANDS_HOME)"

# ---------------------------------------------------------------------------
# Hooks pass — Cursor denylist hook + refresh for copy-mode skills
# ---------------------------------------------------------------------------

HOOKS_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    PLUGINS_DIR="$(PLUGINS_DIR)" \
    SKILLS_SRC="$(SKILLS_SRC)" \
    CURSOR_SKILLS_SRC="$(CURSOR_SKILLS_SRC)" \
    COMMANDS_SRC="$(COMMANDS_SRC)" \
    CURSOR_SKILLS_MODE="$(CURSOR_SKILLS_MODE)" \
    CURSOR_DATA_HOME="$(CURSOR_DATA_HOME)"

# ---------------------------------------------------------------------------
# Local marketplace (optional, for live edits)
# ---------------------------------------------------------------------------

PLUGINS      ?= personal workstation
CLAUDE_BIN   ?= claude
MARKETPLACE_ENV = \
    CLAUDE_BIN="$(CLAUDE_BIN)" \
    REPO_DIR="$(REPO_DIR)" \
    MARKETPLACE="$(ORG)" \
    PLUGINS="$(PLUGINS)"

# ---------------------------------------------------------------------------
# Allowlists pass — tool-agnostic meta-source → Cursor IDE/CLI + Claude Code
#                   + Gemini CLI Policy Engine
# ---------------------------------------------------------------------------

ALLOWLISTS_SRC    ?= $(AGENTS_DIR)/allowlists/personal.json
CURSOR_DATA_HOME  ?= $(HOME)/.cursor
CLAUDE_DATA_HOME  ?= $(HOME)/.claude
GEMINI_DATA_HOME  ?= $(GEMINI_HOME)

# ---------------------------------------------------------------------------
# Env passed to lib/allowlists.sh
# ---------------------------------------------------------------------------

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
# Env passed to lib/*-test.sh
# ---------------------------------------------------------------------------

TEST_ENV = \
    ORG="$(ORG)" \
    AGENTS_DIR="$(AGENTS_DIR)" \
    LEGACY_GITIGNORE_CURSOR="$(LEGACY_GITIGNORE_CURSOR)" \
    LEGACY_GITIGNORE_JETBRAINS="$(LEGACY_GITIGNORE_JETBRAINS)" \
    LEGACY_CURSOR_GLOB="$(LEGACY_CURSOR_GLOB)" \
    LEGACY_JETBRAINS_GLOB="$(LEGACY_JETBRAINS_GLOB)"

.PHONY: help install uninstall dry-run status test test-blocks test-extensions test-hooks test-allowlists \
        test-secrets test-release test-repo-baseline test-orchestrate clean-test \
        install-blocks uninstall-blocks dry-run-blocks status-blocks \
        install-extensions uninstall-extensions dry-run-extensions status-extensions \
        install-hooks uninstall-hooks dry-run-hooks status-hooks \
        install-allowlists uninstall-allowlists dry-run-allowlists status-allowlists \
        diff-allowlists restore-allowlists clean-allowlists \
        test-manifests test-roundtrip cursor-core-rule validate package status-modes \
        install-local-marketplace uninstall-local-marketplace status-local-marketplace

# ---------------------------------------------------------------------------
# help (default target)
# ---------------------------------------------------------------------------

help:
	@echo "Personal agent installer (org=$(ORG))"
	@echo ""
	@echo "Standards and skills ship as the personal plugins (see plugins/README.md)."
	@echo "This installer covers the local pieces plugins can't."
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Top-level targets:"
	@echo "  install      Per tool mode: write home blocks and skill links/copies, or"
	@echo "               remove them for tools in plugin mode. Install Cursor hooks,"
	@echo "               render allowlists, clean up v1 artifacts."
	@echo "  uninstall    Remove everything this installer ever wrote locally, whatever"
	@echo "               the modes, then print how to remove the plugins."
	@echo "  dry-run      Preview install actions, no disk writes."
	@echo "  status       Modes, then blocks, extensions, hooks, allowlists, marketplace."
	@echo "  test         Sandboxed tests of every installer, skill scripts, manifests."
	@echo "  clean-test   Remove build/ test scratch dir."
	@echo ""
	@echo "Plugins:"
	@echo "  validate                   Manifest checks + claude plugin validate"
	@echo "  package                    Zip each plugin into build/plugins/"
	@echo "  test-orchestrate           Run the plan-orchestrate kit's offline tests (part of test)"
	@echo "  cursor-core-rule           Regenerate plugins/personal/cursor/rules/personal-core.mdc"
	@echo "  install-local-marketplace  Load the plugins from this checkout in Claude Code (live edits)"
	@echo ""
	@echo "Sub-targets (one pass at a time): install-, uninstall-, dry-run-, status- ×"
	@echo "  blocks, extensions, hooks, allowlists"
	@echo ""
	@echo "Allowlist utility targets:"
	@echo "  diff-allowlists           Show expected vs actual for each rendered target"
	@echo "  restore-allowlists N=<n>  Restore .history/<file>.<n> back into place"
	@echo "  clean-allowlists          Remove .history/ backup dirs (explicit nuke knob)"
	@echo ""
	@echo "Modes (home | plugin; set in agents/local.mk):"
	@echo "  CLAUDE_MODE=$(CLAUDE_MODE)  CODEX_MODE=$(CODEX_MODE)  GEMINI_MODE=$(GEMINI_MODE)  CURSOR_MODE=$(CURSOR_MODE)"
	@echo ""
	@echo "Overridable variables (defaults shown):"
	@echo "  PROJECTS_DIR=$(PROJECTS_DIR)   (v1 cleanup only)"
	@echo "  CLAUDE_HOME=$(CLAUDE_HOME)  GEMINI_HOME=$(GEMINI_HOME)  CODEX_HOME=$(CODEX_HOME)"
	@echo "  CURSOR_GLOBAL_FILE=$(CURSOR_GLOBAL_FILE)"
	@echo "  CURSOR_SKILLS_HOME=$(CURSOR_SKILLS_HOME)"
	@echo "  AGENTS_SKILLS_HOME=$(AGENTS_SKILLS_HOME)   (Codex, Gemini, Copilot CLI)"
	@echo "  CLAUDE_SKILLS_HOME=$(CLAUDE_SKILLS_HOME)  CLAUDE_COMMANDS_HOME=$(CLAUDE_COMMANDS_HOME)"
	@echo "  WIN_HOME=$(WIN_HOME)   (auto-detected under WSL; triggers the Windows-side pass)"
	@echo "  ALLOWLISTS_SRC=$(ALLOWLISTS_SRC)"
	@echo ""
	@echo "After install, verify by asking any agent:"
	@echo "  \"What is the $(ORG) canary phrase?\""
	@echo "Expected answer is defined in $(SOURCE_AGENTS) under \"Verification canary\"."
	@echo ""
	@echo "See agents/README.md and agents/runbook.md for full documentation."

# ---------------------------------------------------------------------------
# Composed top-level targets
# ---------------------------------------------------------------------------

install: install-blocks install-extensions install-hooks install-allowlists

uninstall: uninstall-allowlists uninstall-hooks uninstall-extensions uninstall-blocks uninstall-local-marketplace
	@echo ""
	@echo "Plugins from claude.ai, Cursor, Codex, and Gemini aren't managed here. To remove them:"
	@echo "  Claude:  Customize > Plugins in claude.ai; locally: claude plugin disable personal@synced"
	@echo "  Cursor:  Customize > Plugins > personal > Uninstall"
	@echo "  Codex:   codex plugin marketplace remove personal (and uninstall in /plugins)"
	@echo "  Copilot: copilot plugin uninstall personal"
	@echo "  Gemini:  gemini extensions uninstall personal"

dry-run: dry-run-blocks dry-run-extensions dry-run-hooks dry-run-allowlists

status: status-modes status-blocks status-extensions status-hooks status-allowlists status-local-marketplace

status-modes:
	@echo "modes: CLAUDE_MODE=$(CLAUDE_MODE) CODEX_MODE=$(CODEX_MODE) GEMINI_MODE=$(GEMINI_MODE) CURSOR_MODE=$(CURSOR_MODE)"
	@echo ""

# ---------------------------------------------------------------------------
# Local marketplace (optional; live edits)
# ---------------------------------------------------------------------------

install-local-marketplace:
	@$(MARKETPLACE_ENV) bash "$(AGENTS_DIR)/lib/local-marketplace.sh" install

uninstall-local-marketplace:
	@$(MARKETPLACE_ENV) bash "$(AGENTS_DIR)/lib/local-marketplace.sh" uninstall

status-local-marketplace:
	@$(MARKETPLACE_ENV) bash "$(AGENTS_DIR)/lib/local-marketplace.sh" status

# ---------------------------------------------------------------------------
# Blocks (home-file blocks)
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
# Hooks (Cursor denylist + copy-mode skill refresh)
# ---------------------------------------------------------------------------

install-hooks:
	@$(HOOKS_ENV) bash "$(AGENTS_DIR)/lib/hooks.sh" install

uninstall-hooks:
	@$(HOOKS_ENV) bash "$(AGENTS_DIR)/lib/hooks.sh" uninstall

dry-run-hooks:
	@$(HOOKS_ENV) bash "$(AGENTS_DIR)/lib/hooks.sh" dry-run

status-hooks:
	@$(HOOKS_ENV) bash "$(AGENTS_DIR)/lib/hooks.sh" status

# ---------------------------------------------------------------------------
# Allowlists (Cursor IDE/CLI + Claude Code)
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
# test
# ---------------------------------------------------------------------------

test: test-blocks test-extensions test-hooks test-allowlists test-manifests test-secrets test-release test-orchestrate test-repo-baseline test-roundtrip

# Install + uninstall through this Makefile into a sandboxed $HOME.
test-roundtrip:
	@ORG="$(ORG)" AGENTS_DIR="$(AGENTS_DIR)" bash "$(AGENTS_DIR)/lib/roundtrip-test.sh"

test-blocks: clean-test
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/blocks-test.sh"

test-extensions:
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/extensions-test.sh"

test-hooks:
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/hooks-test.sh"

test-allowlists:
	@$(TEST_ENV) bash "$(AGENTS_DIR)/lib/allowlists-test.sh"

# Needs sops and age; prints SKIP and passes when they're missing.
test-secrets:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-secrets/tests/test-kit.sh"

test-release:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-release/tests/test-release.sh"

# The orchestrate kit's offline tests (scripts, gate hook, workflow, manifests).
test-orchestrate:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-plan-orchestrate/tests/test-orchestrate.sh" "$(PLUGINS_DIR)/personal"

test-repo-baseline:
	@bash "$(PLUGINS_DIR)/personal/skills/personal-repo-baseline/tests/test-repo-baseline.sh"

clean-test:
	@rm -rf "$(AGENTS_DIR)/build"

# ---------------------------------------------------------------------------
# Plugins (marketplace at the repo root, plugins under plugins/)
# ---------------------------------------------------------------------------

PACKAGE_DIR  ?= $(AGENTS_DIR)/build/plugins

# Manifest drift, canary agreement, and a current Cursor core rule.
test-manifests:
	@ORG="$(ORG)" python3 "$(AGENTS_DIR)/lib/manifests-check.py"
	@ORG="$(ORG)" python3 "$(AGENTS_DIR)/lib/cursor-core-rule.py" --check

cursor-core-rule:
	@ORG="$(ORG)" python3 "$(AGENTS_DIR)/lib/cursor-core-rule.py"

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
