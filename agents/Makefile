SHELL := /bin/zsh
.DEFAULT_GOAL := install

PROJECTS_DIR  ?= $(HOME)/Projects
REPO_ROOT     := $(realpath $(CURDIR)/..)
AGENTS_DIR    ?= $(CURDIR)
CURSOR_SRC    ?= $(AGENTS_DIR)/cursor
CURSOR_IGNORE := .cursor/rules/personal-*.mdc

CLAUDE_HOME   ?= $(HOME)/.claude
GEMINI_HOME   ?= $(HOME)/.gemini
CODEX_HOME    ?= $(HOME)/.codex
XCODE_CLAUDE  ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig
XCODE_CODEX   ?= $(HOME)/Library/Developer/Xcode/CodingAssistant/codex

HAS_XCODE  := $(shell test -d /Applications/Xcode.app && \
                test -d "$(HOME)/Library/Developer/Xcode/CodingAssistant" && echo 1)
HAS_CURSOR := $(shell test -d /Applications/Cursor.app && echo 1 || command -v cursor >/dev/null 2>&1 && echo 1)

BUILD_DIR     := $(CURDIR)/build
TEST_DIR      := $(BUILD_DIR)/test
TEST_HOME     := $(TEST_DIR)/.home

# Resolve symlinks so find results match path comparisons
# (~/Projects is commonly a symlink to another location)
FIND_REPOS = find "$(realpath $(1))" \
	\( -name node_modules -o -name .build -o -name Pods -o -name __pycache__ \
	   -o -name .tox -o -name .venv -o -name venv -o -name .gradle \
	   -o -name DerivedData -o -name .cache \) -prune \
	-o -name .git \( -type d -o -type f \) -print

.PHONY: install uninstall status claude gemini codex xcode cursor sync sync-check test clean-test

# ---------------------------------------------------------------------------
# sync: regenerate AGENTS.md from SHARED.md
# ---------------------------------------------------------------------------
# Codex CLI does not support `@` imports, so AGENTS.md must be a fully
# inlined copy of SHARED.md. The only difference is the path to standards/:
# SHARED.md uses `../standards/` (relative to agents/), while AGENTS.md uses
# `standards/` (relative to the repo root, where Codex expects it).

sync:
	@sed 's|\.\./standards/|standards/|g' "$(AGENTS_DIR)/SHARED.md" > "$(AGENTS_DIR)/AGENTS.md"
	@echo "synced:    AGENTS.md <- SHARED.md"

sync-check:
	@if ! diff -q <(sed 's|\.\./standards/|standards/|g' "$(AGENTS_DIR)/SHARED.md") "$(AGENTS_DIR)/AGENTS.md" >/dev/null; then \
		echo "FAIL: AGENTS.md is out of sync with SHARED.md — run 'make sync'"; \
		diff <(sed 's|\.\./standards/|standards/|g' "$(AGENTS_DIR)/SHARED.md") "$(AGENTS_DIR)/AGENTS.md" || true; \
		exit 1; \
	fi
	@echo "sync:      AGENTS.md matches SHARED.md"

# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

install: sync claude gemini codex xcode cursor
	@echo ""
	@echo "done"

# ---------------------------------------------------------------------------
# global: claude
# ---------------------------------------------------------------------------

claude:
	@mkdir -p "$(CLAUDE_HOME)"
	@printf '%s\n' '@~/Projects/personal/public/agents/CLAUDE.md' > "$(CLAUDE_HOME)/CLAUDE.md"
	@echo "installed: claude  -> $(CLAUDE_HOME)/CLAUDE.md"

# ---------------------------------------------------------------------------
# global: gemini
# ---------------------------------------------------------------------------

gemini:
	@mkdir -p "$(GEMINI_HOME)"
	@printf '%s\n' '@~/Projects/personal/public/agents/GEMINI.md' > "$(GEMINI_HOME)/GEMINI.md"
	@echo "installed: gemini  -> $(GEMINI_HOME)/GEMINI.md"

# ---------------------------------------------------------------------------
# global: codex
# ---------------------------------------------------------------------------

codex:
	@mkdir -p "$(CODEX_HOME)"
	@ln -sf "$(AGENTS_DIR)/AGENTS.md" "$(CODEX_HOME)/AGENTS.md"
	@echo "installed: codex   -> $(CODEX_HOME)/AGENTS.md"

# ---------------------------------------------------------------------------
# global: xcode (skipped when Xcode is not installed)
# ---------------------------------------------------------------------------

xcode:
ifdef HAS_XCODE
	@mkdir -p "$(XCODE_CLAUDE)"
	@printf '%s\n' '@~/Projects/personal/public/agents/CLAUDE.md' > "$(XCODE_CLAUDE)/CLAUDE.md"
	@echo "installed: xcode   -> $(XCODE_CLAUDE)/CLAUDE.md"
	@mkdir -p "$(XCODE_CODEX)"
	@ln -sf "$(AGENTS_DIR)/AGENTS.md" "$(XCODE_CODEX)/AGENTS.md"
	@echo "installed: xcode   -> $(XCODE_CODEX)/AGENTS.md"
else
	@echo "skipped:   xcode   (not installed)"
endif

# ---------------------------------------------------------------------------
# per-project: cursor (skipped when Cursor is not installed)
# ---------------------------------------------------------------------------

cursor:
ifdef HAS_CURSOR
	@count=0; skipped=0; \
	while IFS= read -r gitdir; do \
		project=$${gitdir%/.git}; \
		if [ "$$project" = "$(REPO_ROOT)" ]; then skipped=$$((skipped + 1)); continue; fi; \
		nested=0; \
		parent="$$project"; \
		while parent=$$(dirname "$$parent"); do \
			case "$$parent" in "$(realpath $(PROJECTS_DIR))"|/) break;; esac; \
			if [ -e "$$parent/.git" ]; then nested=1; break; fi; \
		done; \
		if [ "$$nested" -eq 1 ]; then skipped=$$((skipped + 1)); continue; fi; \
		rules="$$project/.cursor/rules"; \
		mkdir -p "$$rules"; \
		find "$$rules" -maxdepth 1 -name 'personal-*.mdc' -type l -delete; \
		for src in "$(CURSOR_SRC)"/*.mdc; do \
			ln -sf "$$src" "$$rules/$$(basename "$$src")"; \
		done; \
		gitignore="$$project/.gitignore"; \
		if ! grep -qxF '$(CURSOR_IGNORE)' "$$gitignore" 2>/dev/null; then \
			if [ -s "$$gitignore" ] && [ -n "$$(tail -c 1 "$$gitignore")" ]; then \
				printf '\n' >> "$$gitignore"; \
			fi; \
			printf '%s\n' '$(CURSOR_IGNORE)' >> "$$gitignore"; \
		fi; \
		count=$$((count + 1)); \
	done < <($(call FIND_REPOS,$(PROJECTS_DIR))); \
	echo "installed: cursor  -> $$count projects under $(PROJECTS_DIR) ($$skipped skipped)"
else
	@echo "skipped:   cursor  (not installed)"
endif

# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

uninstall:
	@rm -f "$(CLAUDE_HOME)/CLAUDE.md" && echo "removed:   claude  -> $(CLAUDE_HOME)/CLAUDE.md" || true
	@rm -f "$(GEMINI_HOME)/GEMINI.md" && echo "removed:   gemini  -> $(GEMINI_HOME)/GEMINI.md" || true
	@rm -f "$(CODEX_HOME)/AGENTS.md"  && echo "removed:   codex   -> $(CODEX_HOME)/AGENTS.md"  || true
	@rm -f "$(XCODE_CLAUDE)/CLAUDE.md" 2>/dev/null && echo "removed:   xcode   -> $(XCODE_CLAUDE)/CLAUDE.md" || true
	@rm -f "$(XCODE_CODEX)/AGENTS.md"  2>/dev/null && echo "removed:   xcode   -> $(XCODE_CODEX)/AGENTS.md"  || true
	@count=0; \
	while IFS= read -r gitdir; do \
		project=$${gitdir%/.git}; \
		rules="$$project/.cursor/rules"; \
		if [ -d "$$rules" ]; then \
			find "$$rules" -maxdepth 1 -name 'personal-*.mdc' -type l -delete; \
		fi; \
		gitignore="$$project/.gitignore"; \
		if [ -f "$$gitignore" ]; then \
			grep -vxF '$(CURSOR_IGNORE)' "$$gitignore" > "$$gitignore.tmp" || true; \
			mv "$$gitignore.tmp" "$$gitignore"; \
			if [ ! -s "$$gitignore" ]; then rm -f "$$gitignore"; fi; \
		fi; \
		count=$$((count + 1)); \
	done < <($(call FIND_REPOS,$(PROJECTS_DIR))); \
	echo "removed:   cursor  -> $$count projects under $(PROJECTS_DIR)"
	@echo ""
	@echo "done"

# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

define check_file
	@if [ -e "$(1)" ]; then \
		echo "  ✓ $(2)"; \
	else \
		echo "  ✗ $(2)"; \
	fi
endef

status:
	@echo "=== AI Agent Rules Status ==="
	@echo ""
	@echo "global:"
	$(call check_file,$(CLAUDE_HOME)/CLAUDE.md,claude  $(CLAUDE_HOME)/CLAUDE.md)
	$(call check_file,$(GEMINI_HOME)/GEMINI.md,gemini  $(GEMINI_HOME)/GEMINI.md)
	$(call check_file,$(CODEX_HOME)/AGENTS.md,codex   $(CODEX_HOME)/AGENTS.md)
	$(call check_file,$(XCODE_CLAUDE)/CLAUDE.md,xcode   $(XCODE_CLAUDE)/CLAUDE.md)
	$(call check_file,$(XCODE_CODEX)/AGENTS.md,xcode   $(XCODE_CODEX)/AGENTS.md)
	@echo ""
	@echo "cursor ($(PROJECTS_DIR)):"
	@total=0; linked=0; \
	while IFS= read -r gitdir; do \
		project=$${gitdir%/.git}; \
		if [ "$$project" = "$(REPO_ROOT)" ]; then continue; fi; \
		nested=0; \
		parent="$$project"; \
		while parent=$$(dirname "$$parent"); do \
			case "$$parent" in "$(realpath $(PROJECTS_DIR))"|/) break;; esac; \
			if [ -e "$$parent/.git" ]; then nested=1; break; fi; \
		done; \
		if [ "$$nested" -eq 1 ]; then continue; fi; \
		total=$$((total + 1)); \
		rules="$$project/.cursor/rules"; \
		if [ -L "$$rules/personal-main.mdc" ]; then \
			linked=$$((linked + 1)); \
		fi; \
	done < <($(call FIND_REPOS,$(PROJECTS_DIR))); \
	echo "  $$linked/$$total repos have cursor rules"
	@echo ""
	@echo "detection:"
	@if [ -d /Applications/Xcode.app ] && [ -d "$(HOME)/Library/Developer/Xcode/CodingAssistant" ]; then \
		echo "  ✓ xcode"; \
	else \
		echo "  ✗ xcode"; \
	fi
	@if [ -d /Applications/Cursor.app ] || command -v cursor >/dev/null 2>&1; then \
		echo "  ✓ cursor"; \
	else \
		echo "  ✗ cursor"; \
	fi

# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

clean-test:
	@rm -rf "$(BUILD_DIR)"

test: clean-test sync-check
	@echo ""
	@echo "=== setting up fixtures ==="
	@mkdir -p "$(TEST_DIR)/normal-repo"             && git -C "$(TEST_DIR)/normal-repo" init -q
	@mkdir -p "$(TEST_DIR)/gitignore-newline"        && git -C "$(TEST_DIR)/gitignore-newline" init -q \
		&& printf '*.log\n.DS_Store\n' > "$(TEST_DIR)/gitignore-newline/.gitignore"
	@mkdir -p "$(TEST_DIR)/gitignore-no-newline"     && git -C "$(TEST_DIR)/gitignore-no-newline" init -q \
		&& printf '*.log\n.DS_Store' > "$(TEST_DIR)/gitignore-no-newline/.gitignore"
	@mkdir -p "$(TEST_DIR)/already-ignored"          && git -C "$(TEST_DIR)/already-ignored" init -q \
		&& printf '*.log\n$(CURSOR_IGNORE)\n' > "$(TEST_DIR)/already-ignored/.gitignore"
	@mkdir -p "$(TEST_DIR)/parent-repo/nested-repo"  && git -C "$(TEST_DIR)/parent-repo" init -q \
		&& git -C "$(TEST_DIR)/parent-repo/nested-repo" init -q
	@mkdir -p "$(TEST_DIR)/existing-rules/.cursor/rules" && git -C "$(TEST_DIR)/existing-rules" init -q \
		&& echo "custom rule" > "$(TEST_DIR)/existing-rules/.cursor/rules/team-rule.mdc"
	@mkdir -p "$(TEST_DIR)/empty-gitignore"          && git -C "$(TEST_DIR)/empty-gitignore" init -q \
		&& touch "$(TEST_DIR)/empty-gitignore/.gitignore"
	@mkdir -p "$(TEST_DIR)/path with spaces"         && git -C "$(TEST_DIR)/path with spaces" init -q
	@mkdir -p "$(TEST_DIR)/worktree-repo" \
		&& printf 'gitdir: $(TEST_DIR)/normal-repo/.git/worktrees/worktree-repo\n' > "$(TEST_DIR)/worktree-repo/.git"
	@echo "fixtures: 9 repos + 1 nested (1 worktree)"
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== install ==="
	@$(MAKE) -f "$(CURDIR)/Makefile" install \
		PROJECTS_DIR="$(TEST_DIR)" \
		CLAUDE_HOME="$(TEST_HOME)/.claude" \
		GEMINI_HOME="$(TEST_HOME)/.gemini" \
		CODEX_HOME="$(TEST_HOME)/.codex" \
		XCODE_CLAUDE="$(TEST_HOME)/xcode-claude" \
		XCODE_CODEX="$(TEST_HOME)/xcode-codex" \
		HAS_CURSOR=1 HAS_XCODE=1
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== verify install ==="
	@fail=0; \
	for repo in normal-repo gitignore-newline gitignore-no-newline already-ignored parent-repo existing-rules empty-gitignore "path with spaces" worktree-repo; do \
		if [ ! -L "$(TEST_DIR)/$$repo/.cursor/rules/personal-main.mdc" ]; then \
			echo "FAIL: $$repo missing cursor rules"; fail=1; \
		fi; \
		if ! grep -qxF '$(CURSOR_IGNORE)' "$(TEST_DIR)/$$repo/.gitignore" 2>/dev/null; then \
			echo "FAIL: $$repo missing .gitignore entry"; fail=1; \
		fi; \
	done; \
	if [ -d "$(TEST_DIR)/parent-repo/nested-repo/.cursor/rules" ]; then \
		echo "FAIL: nested-repo should not have cursor rules"; fail=1; \
	fi; \
	count=$$(grep -cxF '$(CURSOR_IGNORE)' "$(TEST_DIR)/already-ignored/.gitignore"); \
	if [ "$$count" -ne 1 ]; then \
		echo "FAIL: already-ignored has $$count entries (expected 1)"; fail=1; \
	fi; \
	if [ ! -f "$(TEST_DIR)/existing-rules/.cursor/rules/team-rule.mdc" ]; then \
		echo "FAIL: team-rule.mdc was deleted"; fail=1; \
	fi; \
	content=$$(cat "$(TEST_DIR)/gitignore-no-newline/.gitignore"); \
	line2=$$(echo "$$content" | sed -n '2p'); \
	if [ "$$line2" != ".DS_Store" ]; then \
		echo "FAIL: gitignore-no-newline has corrupted lines"; fail=1; \
	fi; \
	if [ -e "$(TEST_HOME)/.claude/CLAUDE.md" ] && [ -e "$(TEST_HOME)/.gemini/GEMINI.md" ] \
		&& [ -L "$(TEST_HOME)/.codex/AGENTS.md" ] \
		&& [ -e "$(TEST_HOME)/xcode-claude/CLAUDE.md" ] && [ -L "$(TEST_HOME)/xcode-codex/AGENTS.md" ]; then \
		true; \
	else \
		echo "FAIL: global configs missing"; fail=1; \
	fi; \
	if [ "$$fail" -eq 0 ]; then echo "install: all checks passed"; else exit 1; fi
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== verify idempotency ==="
	@$(MAKE) -f "$(CURDIR)/Makefile" install \
		PROJECTS_DIR="$(TEST_DIR)" \
		CLAUDE_HOME="$(TEST_HOME)/.claude" \
		GEMINI_HOME="$(TEST_HOME)/.gemini" \
		CODEX_HOME="$(TEST_HOME)/.codex" \
		XCODE_CLAUDE="$(TEST_HOME)/xcode-claude" \
		XCODE_CODEX="$(TEST_HOME)/xcode-codex" \
		HAS_CURSOR=1 HAS_XCODE=1
	@fail=0; \
	count=$$(grep -cxF '$(CURSOR_IGNORE)' "$(TEST_DIR)/already-ignored/.gitignore"); \
	if [ "$$count" -ne 1 ]; then \
		echo "FAIL: idempotency - already-ignored has $$count entries"; fail=1; \
	fi; \
	count=$$(grep -cxF '$(CURSOR_IGNORE)' "$(TEST_DIR)/normal-repo/.gitignore"); \
	if [ "$$count" -ne 1 ]; then \
		echo "FAIL: idempotency - normal-repo has $$count entries"; fail=1; \
	fi; \
	if [ "$$fail" -eq 0 ]; then echo "idempotency: all checks passed"; else exit 1; fi
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== uninstall ==="
	@$(MAKE) -f "$(CURDIR)/Makefile" uninstall \
		PROJECTS_DIR="$(TEST_DIR)" \
		CLAUDE_HOME="$(TEST_HOME)/.claude" \
		GEMINI_HOME="$(TEST_HOME)/.gemini" \
		CODEX_HOME="$(TEST_HOME)/.codex" \
		XCODE_CLAUDE="$(TEST_HOME)/xcode-claude" \
		XCODE_CODEX="$(TEST_HOME)/xcode-codex"
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== verify uninstall ==="
	@fail=0; \
	for repo in normal-repo gitignore-newline gitignore-no-newline already-ignored parent-repo existing-rules empty-gitignore "path with spaces" worktree-repo; do \
		if find "$(TEST_DIR)/$$repo/.cursor/rules" -maxdepth 1 -name 'personal-*.mdc' -type l 2>/dev/null | grep -q .; then \
			echo "FAIL: $$repo still has personal rules"; fail=1; \
		fi; \
	done; \
	if grep -rqF 'personal-' "$(TEST_DIR)/gitignore-newline/.gitignore" 2>/dev/null; then \
		echo "FAIL: gitignore-newline still has entry"; fail=1; \
	fi; \
	if [ -f "$(TEST_DIR)/normal-repo/.gitignore" ]; then \
		echo "FAIL: normal-repo .gitignore should be deleted (was only our entry)"; fail=1; \
	fi; \
	if [ -f "$(TEST_DIR)/empty-gitignore/.gitignore" ]; then \
		echo "FAIL: empty-gitignore .gitignore should be deleted"; fail=1; \
	fi; \
	if [ -f "$(TEST_DIR)/worktree-repo/.gitignore" ]; then \
		echo "FAIL: worktree-repo .gitignore should be deleted (was only our entry)"; fail=1; \
	fi; \
	if [ ! -f "$(TEST_DIR)/worktree-repo/.git" ]; then \
		echo "FAIL: worktree-repo .git file was removed (should be preserved)"; fail=1; \
	fi; \
	content=$$(cat "$(TEST_DIR)/gitignore-newline/.gitignore" 2>/dev/null); \
	expected=$$(printf '*.log\n.DS_Store'); \
	if [ "$$content" != "$$expected" ]; then \
		echo "FAIL: gitignore-newline content not restored"; fail=1; \
	fi; \
	if [ ! -f "$(TEST_DIR)/existing-rules/.cursor/rules/team-rule.mdc" ]; then \
		echo "FAIL: team-rule.mdc was deleted"; fail=1; \
	fi; \
	if [ -e "$(TEST_HOME)/.claude/CLAUDE.md" ] || [ -e "$(TEST_HOME)/.gemini/GEMINI.md" ] \
		|| [ -L "$(TEST_HOME)/.codex/AGENTS.md" ] \
		|| [ -e "$(TEST_HOME)/xcode-claude/CLAUDE.md" ] || [ -L "$(TEST_HOME)/xcode-codex/AGENTS.md" ]; then \
		echo "FAIL: global configs still present"; fail=1; \
	fi; \
	if [ "$$fail" -eq 0 ]; then echo "uninstall: all checks passed"; else exit 1; fi
	@echo ""
	@# ---------------------------------------------------------------
	@echo "=== verify symlinked PROJECTS_DIR ==="
	@mkdir -p "$(TEST_DIR)/symlink-real/link-repo" && git -C "$(TEST_DIR)/symlink-real/link-repo" init -q
	@ln -sf "$(TEST_DIR)/symlink-real" "$(TEST_DIR)/symlink-alias"
	@$(MAKE) -f "$(CURDIR)/Makefile" cursor \
		PROJECTS_DIR="$(TEST_DIR)/symlink-alias" \
		HAS_CURSOR=1
	@fail=0; \
	if [ ! -L "$(TEST_DIR)/symlink-real/link-repo/.cursor/rules/personal-main.mdc" ]; then \
		echo "FAIL: symlinked PROJECTS_DIR - cursor rules not installed"; fail=1; \
	fi; \
	if [ "$$fail" -eq 0 ]; then echo "symlink: all checks passed"; else exit 1; fi
	@echo ""
	@rm -rf "$(BUILD_DIR)"
	@echo "=== all tests passed ==="
