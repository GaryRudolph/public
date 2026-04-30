SHELL         := /bin/bash
DEST          ?= $(HOME)/Applications
ALL_APPS      := $(sort $(notdir $(basename $(wildcard apps/*.env))))
PROFILES      := $(sort $(notdir $(basename $(wildcard profiles/*.env))))
.DEFAULT_GOAL := help

# Resolve per-app CLI binaries once at parse time.
# CURSOR_BIN fallback path has no spaces; CODE_BIN fallback does, so the
# vscode AppleScript template single-quotes __CODE_BIN__.
CURSOR_BIN := $(shell command -v cursor 2>/dev/null || echo /Applications/Cursor.app/Contents/Resources/app/bin/cursor)
CODE_BIN   := $(shell command -v code   2>/dev/null || echo /Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin/code)

.PHONY: help install uninstall clean check validate-profiles validate-templates dry-run

help:
	@echo "Targets:"
	@echo "  make install                     Build all profiles (only their declared APPS) to $(DEST)"
	@echo "  make install PROFILE=agerpoint   Build one profile"
	@echo "  make uninstall                   Remove all built wrappers from $(DEST)"
	@echo "  make uninstall PROFILE=agerpoint Remove one profile's wrappers"
	@echo "  make dry-run                     Read-only rehearsal of 'make install' (no writes to $(DEST))"
	@echo "  make check                       Verify prereqs (tools and source apps)"
	@echo "  make validate-profiles           Verify every profile's APPS field is present and references known apps"
	@echo "  make validate-templates          Verify each (profile, app) AppleScript renders and osacompiles cleanly"
	@echo "  make clean                       Remove build artifacts"

# Per-profile APPS validation (same as install-% does). Errors fast on missing
# APPS or unknown app slugs.
validate-profiles:
	@for p in $(PROFILES); do \
	    ( . "profiles/$$p.env"; \
	      [[ -n "$${APPS:-}" ]] || { echo "APPS required in profiles/$$p.env (comma-separated app slugs)"; exit 1; }; \
	      for app in $${APPS//,/ }; do \
	          case " $(ALL_APPS) " in \
	              *" $$app "*) ;; \
	              *) echo "unknown app '$$app' in profiles/$$p.env; available: $(ALL_APPS)"; exit 1 ;; \
	          esac; \
	      done ) || exit 1; \
	done

# Render each (profile, app) AppleScript through sed and osacompile-check the
# result in a tmp dir. Catches template syntax errors and bad token values
# before any writes to $(DEST). No icon-pipeline work (covered by check).
validate-templates: validate-profiles
	@for p in $(PROFILES); do \
	    ( . "profiles/$$p.env"; \
	      for app in $${APPS//,/ }; do \
	          work=$$(mktemp -d); \
	          sed -e "s|__SLUG__|$$p|g" \
	              -e "s|__CURSOR_BIN__|$(CURSOR_BIN)|g" \
	              -e "s|__CODE_BIN__|$(CODE_BIN)|g" \
	              "apps/$$app.applescript" > "$$work/script.applescript"; \
	          osacompile -o "$$work/test.scpt" "$$work/script.applescript" >/dev/null 2>&1 \
	              || { echo "render+osacompile failed: profile=$$p app=$$app (apps/$$app.applescript)"; rm -rf "$$work"; exit 1; }; \
	          rm -rf "$$work"; \
	      done ) || exit 1; \
	done

# Read-only rehearsal of 'make install'. Runs the full pre-flight (check +
# validate-profiles + validate-templates) and reports the wrappers install
# would produce, marking each as new or replacing-existing. Touches no files
# under $(DEST). If dry-run succeeds, install will succeed too.
dry-run: check validate-profiles validate-templates
	@echo "Apps:"
	@for a in $(ALL_APPS); do \
	    ( . "apps/$$a.env"; \
	      printf "  %-12s NAME=%-10s SRC=%s\n" "$$a" "$$NAME" "$$SRC" ); \
	done
	@echo "Profiles:"
	@for p in $(PROFILES); do \
	    ( . "profiles/$$p.env"; \
	      printf "  %-12s LABEL=%-6s NAME=%-12s APPS=%s\n" "$$p" "$$LABEL" "$$NAME" "$$APPS" ); \
	done
	@echo "Wrappers (would be built into $(DEST) by 'make install'):"
	@for p in $(PROFILES); do \
	    ( . "profiles/$$p.env"; \
	      printf "  %s:\n" "$$p"; \
	      for app in $${APPS//,/ }; do \
	          ( . "apps/$$app.env"; \
	            out="$(DEST)/$$NAME $$LABEL.app"; \
	            if [[ -d "$$out" ]]; then status="(replaces existing)"; else status="(new)"; fi; \
	            printf "    %-32s %s\n" "$$NAME $$LABEL.app" "$$status" ); \
	      done ); \
	done
	@total=$$( for p in $(PROFILES); do ( . "profiles/$$p.env"; echo "$${APPS//,/ }" ); done | wc -w | tr -d ' ' ); \
	echo ""; \
	echo "Summary: $$total wrapper(s) across $(words $(PROFILES)) profile(s); all pre-flight checks passed."; \
	echo "Run 'make install' to build."

check:
	@command -v osacompile >/dev/null || { echo "missing osacompile (ships with macOS)"; exit 1; }
	@command -v iconutil   >/dev/null || { echo "missing iconutil (ships with macOS)"; exit 1; }
	@command -v sips       >/dev/null || { echo "missing sips (ships with macOS)"; exit 1; }
	@command -v magick     >/dev/null || { echo "missing magick — run: brew install imagemagick"; exit 1; }
	@for app in $(ALL_APPS); do \
	    test -f "apps/$$app.env"         || { echo "missing apps/$$app.env"; exit 1; }; \
	    test -f "apps/$$app.applescript" || { echo "missing apps/$$app.applescript"; exit 1; }; \
	    ( . "apps/$$app.env"; \
	      [[ -n "$${NAME:-}" ]] || { echo "NAME required in apps/$$app.env"; exit 1; }; \
	      [[ -n "$${SRC:-}"  ]] || { echo "SRC required in apps/$$app.env"; exit 1; }; \
	      test -d "$$SRC"        || { echo "$$SRC not found (apps/$$app.env)"; exit 1; } ) || exit 1; \
	done

# Build wrappers for one or all profiles. After sourcing profiles/$$SLUG.env:
# NAME = profile NAME, LABEL = profile LABEL. After `. apps/$$app.env` NAME
# is overridden to the app NAME (Cursor / Claude); LABEL persists. Output
# naming = "$$NAME $$LABEL.app" (e.g. "Cursor AP.app").
#
# Notes on the recipe shape:
# 1. No `install-%` pattern rule because GNU Make 3.81 (shipped with macOS)
#    has a bug where .PHONY pattern rules silently no-op. The documented
#    public API is `make install PROFILE=<slug>`; per-profile sub-targets
#    were never exposed.
# 2. `set -e` at the top instead of `( ... ) || exit 1` per app: bash
#    suppresses `set -e` inside any command that is part of a `||` (or `&&`)
#    chain, so the wrapping `|| exit 1` would silently mask failures inside
#    the subshell (e.g. iconutil bailing out).
# 3. After osacompile, the branded icon is written to both applet.icns and
#    droplet.icns (newer macOS osacompile sets Info.plist CFBundleIconFile
#    to "droplet"; older versions used "applet"), and Assets.car is removed
#    so the loose .icns is actually used (asset catalog otherwise shadows it).
install: check validate-profiles validate-templates
	@set -e; \
	mkdir -p "$(DEST)"; \
	for SLUG in $(if $(PROFILE),$(PROFILE),$(PROFILES)); do \
	    test -f "profiles/$$SLUG.env" || { echo "missing profiles/$$SLUG.env"; exit 1; }; \
	    test -f "profiles/$$SLUG.png" || { echo "missing profiles/$$SLUG.png"; exit 1; }; \
	    . "profiles/$$SLUG.env"; \
	    echo "Building $$SLUG ($$NAME, LABEL=$$LABEL): $${APPS//,/ }"; \
	    for app in $${APPS//,/ }; do \
	        . "apps/$$app.env"; \
	        out="$(DEST)/$$NAME $$LABEL.app"; \
	        work=$$(mktemp -d); \
	        sed -e "s|__SLUG__|$$SLUG|g" \
	            -e "s|__CURSOR_BIN__|$(CURSOR_BIN)|g" \
	            -e "s|__CODE_BIN__|$(CODE_BIN)|g" \
	            "apps/$$app.applescript" > "$$work/script.applescript"; \
	        rm -rf "$$out"; \
	        osacompile -o "$$out" "$$work/script.applescript"; \
	        icon=$$(plutil -extract CFBundleIconFile raw "$$SRC/Contents/Info.plist"); \
	        test -n "$$icon" || { echo "no CFBundleIconFile in $$SRC/Contents/Info.plist"; exit 1; }; \
	        case "$$icon" in *.icns) ;; *) icon="$$icon.icns" ;; esac; \
	        sips -s format png "$$SRC/Contents/Resources/$$icon" \
	            --out "$$work/base.png" -z 1024 1024 >/dev/null; \
	        magick composite -gravity southeast -geometry 512x512+48+48 \
	            "profiles/$$SLUG.png" "$$work/base.png" "$$work/branded.png"; \
	        mkdir -p "$$work/icon.iconset"; \
	        for s in 16 32 64 128 256 512; do \
	            sips -z $$s $$s             "$$work/branded.png" \
	                --out "$$work/icon.iconset/icon_$${s}x$${s}.png"     >/dev/null; \
	            sips -z $$((s*2)) $$((s*2)) "$$work/branded.png" \
	                --out "$$work/icon.iconset/icon_$${s}x$${s}@2x.png" >/dev/null; \
	        done; \
	        sips -z 1024 1024 "$$work/branded.png" \
	            --out "$$work/icon.iconset/icon_512x512@2x.png" >/dev/null; \
	        iconutil -c icns "$$work/icon.iconset" -o "$$out/Contents/Resources/applet.icns"; \
	        cp "$$out/Contents/Resources/applet.icns" "$$out/Contents/Resources/droplet.icns"; \
	        rm -f "$$out/Contents/Resources/Assets.car"; \
	        touch "$$out"; \
	        rm -rf "$$work"; \
	        echo "  built $$NAME $$LABEL.app"; \
	    done; \
	done; \
	killall Finder Dock 2>/dev/null || true

# Best-effort cleanup: loops $(ALL_APPS) (not the profile's APPS list), so
# wrappers from a previous APPS configuration get removed too. rm -rf is a
# no-op for non-existent paths. Same recipe shape as install (set -e + inline
# loop, no pattern rule).
uninstall:
	@set -e; \
	for SLUG in $(if $(PROFILE),$(PROFILE),$(PROFILES)); do \
	    test -f "profiles/$$SLUG.env" || { echo "missing profiles/$$SLUG.env"; exit 1; }; \
	    . "profiles/$$SLUG.env"; \
	    for app in $(ALL_APPS); do \
	        . "apps/$$app.env"; \
	        rm -rf "$(DEST)/$$NAME $$LABEL.app"; \
	        echo "Removed $$NAME $$LABEL.app from $(DEST)"; \
	    done; \
	done

clean:
	@rm -rf build
