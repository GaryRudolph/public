#!/usr/bin/env bash
# Block-marker installer for AGENTS.md-style global agent configuration,
# plus the per-repo GitHub Copilot fan-out for organizations that need it.
#
# Manages a single $ORG-keyed block in each home configuration file, leaving
# all other content byte-for-byte intact. Also cleans up legacy v1 per-project
# artifacts (Cursor / JetBrains symlinks and matching .gitignore entries).
#
# When $COPILOT_SRC is set, also fans out two per-repo files
# (.github/copilot-instructions.md and .github/workflows/copilot-setup-steps.yml)
# to every git repo under $PROJECTS_DIR, skipping $REPO_ROOT and nested repos.
# These are NOT v1 artifacts — they are load-bearing for GitHub Copilot Cloud
# Agent (see standards/ticket-to-pr-setup.md). They live committed in each
# repo because Cloud Agent runs in a GitHub-managed VM with no access to your
# home directory.
#
# Required env (set by the calling Makefile):
#   ORG               installer identity ("agerpoint", "personal", ...)
#   SOURCE_AGENTS     absolute path to the canonical AGENTS.md
#   MAKEFILE_LABEL    human-readable label for the "managed by" line
#
# Home-file locations (Makefile passes its preferred defaults):
#   CLAUDE_HOME, GEMINI_HOME, CODEX_HOME
#   CURSOR_GLOBAL_FILE
#   XCODE_CLAUDE_DIR, XCODE_CODEX_DIR
#
# Sibling-repo scan (legacy cleanup + copilot fan-out):
#   PROJECTS_DIR                 sibling-repo scan root
#   REPO_ROOT                    this installer's own repo (skipped during fan-out)
#   LEGACY_GITIGNORE_CURSOR      gitignore line to remove (cursor)
#   LEGACY_GITIGNORE_JETBRAINS   gitignore line to remove (jetbrains, optional)
#   LEGACY_CURSOR_GLOB           filename glob for cursor symlinks
#   LEGACY_JETBRAINS_GLOB        filename glob for jetbrains symlinks (optional)
#
# Copilot fan-out (set only by orgs that drive Ticket-to-PR; bok yes, personal no):
#   COPILOT_SRC                  directory holding copilot-instructions.md +
#                                copilot-setup-steps.yml templates. When unset,
#                                the fan-out is a no-op.
#
# WSL -> Windows-host dual install:
#   WIN_HOME                     If set or auto-detected when /proc/version
#                                contains "microsoft", a second install pass
#                                runs against this path using FULLY INLINED
#                                content (not @-imports) in every home file.
#
# Subcommands:
#   install      Legacy cleanup, write/update the ORG block in each home file,
#                fan out Copilot files (idempotent: only writes when missing
#                or content differs from source).
#   uninstall    Legacy cleanup, remove the ORG block from each home file,
#                remove Copilot files from every sibling repo's working tree.
#   dry-run      Show what install would do; no disk writes.
#   status       Report block presence, fan-out state, and v1 artifacts.

set -euo pipefail

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

: "${ORG:?ORG must be set}"
: "${SOURCE_AGENTS:?SOURCE_AGENTS must be set}"
: "${MAKEFILE_LABEL:=${SOURCE_AGENTS%/*}/Makefile}"

: "${CLAUDE_HOME:=$HOME/.claude}"
: "${GEMINI_HOME:=$HOME/.gemini}"
: "${CODEX_HOME:=$HOME/.codex}"
: "${CURSOR_GLOBAL_FILE:=$HOME/AGENTS.md}"
: "${XCODE_CLAUDE_DIR:=$HOME/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig}"
: "${XCODE_CODEX_DIR:=$HOME/Library/Developer/Xcode/CodingAssistant/codex}"

: "${PROJECTS_DIR:=}"
: "${REPO_ROOT:=}"
: "${LEGACY_GITIGNORE_CURSOR:=}"
: "${LEGACY_GITIGNORE_JETBRAINS:=}"
: "${LEGACY_CURSOR_GLOB:=}"
: "${LEGACY_JETBRAINS_GLOB:=}"

: "${COPILOT_SRC:=}"

: "${WIN_HOME:=}"

# Set by subcommand dispatch; functions check this before writing.
MODE="install"            # install | uninstall | dry-run | status
DRY_RUN=0

# Accumulators printed at the end of every run.
CONFLICTS=()              # one message per committed v1 file detected

# ---------------------------------------------------------------------------
# Detection: WSL + Windows-host home
# ---------------------------------------------------------------------------

is_wsl() {
    [ -r /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null
}

detect_win_home() {
    # Only attempt detection when running under WSL.
    is_wsl || return 1

    # cmd.exe interop must be available.
    command -v cmd.exe >/dev/null 2>&1 || return 1
    command -v wslpath >/dev/null 2>&1 || return 1

    local userprofile wsl_path
    userprofile=$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' || true)
    [ -n "$userprofile" ] || return 1

    wsl_path=$(wslpath "$userprofile" 2>/dev/null || true)
    [ -n "$wsl_path" ] && [ -d "$wsl_path" ] || return 1

    printf '%s' "$wsl_path"
}

# Populate WIN_HOME if WSL is detected and the caller did not override it.
init_win_home() {
    if [ -n "$WIN_HOME" ]; then
        return
    fi
    if is_wsl; then
        local detected
        if detected=$(detect_win_home 2>/dev/null); then
            WIN_HOME="$detected"
        else
            printf 'note: WSL detected but Windows host home could not be resolved\n' >&2
            printf '      (cmd.exe interop or wslpath unavailable; Windows-native\n' >&2
            printf '      tools will not see the standards until this is fixed)\n' >&2
        fi
    fi
}

# ---------------------------------------------------------------------------
# Markers and pretty path
# ---------------------------------------------------------------------------

open_marker() { printf '# >>> %s >>>\n' "$ORG"; }
close_marker() { printf '# <<< %s <<<\n' "$ORG"; }
managed_line() { printf '# managed by %s -- do not edit by hand\n' "$MAKEFILE_LABEL"; }

# Shorten an absolute path for display: $HOME -> ~, otherwise as-is.
pretty_path() {
    local p="$1"
    case "$p" in
        "$HOME"/*) printf '~/%s' "${p#"$HOME"/}" ;;
        *)         printf '%s' "$p" ;;
    esac
}

# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------

# Build the new block (markers + managed line + content) into a temp file.
# Args: $1 = output temp file, $2 = file containing block content (between markers)
build_block_file() {
    local out="$1"
    local content_file="$2"
    {
        open_marker
        managed_line
        cat "$content_file"
        close_marker
    } > "$out"
}

# Extract the current block (everything between OPEN and CLOSE, exclusive of
# the markers themselves) from a file. Writes to stdout. Prints nothing when
# the block is absent.
extract_block_body() {
    local file="$1"
    [ -f "$file" ] || return 0
    awk -v open_m="$(open_marker | tr -d '\n')" -v close_m="$(close_marker | tr -d '\n')" '
        $0 == open_m { in_block=1; next }
        $0 == close_m && in_block { in_block=0; next }
        in_block { print }
    ' "$file"
}

# Extract the WHOLE block including markers; produces the same bytes that
# build_block_file would write, suitable for byte-exact "no change" diffing.
extract_full_block() {
    local file="$1"
    [ -f "$file" ] || return 0
    awk -v open_m="$(open_marker | tr -d '\n')" -v close_m="$(close_marker | tr -d '\n')" '
        $0 == open_m { in_block=1 }
        in_block { print }
        $0 == close_m && in_block { in_block=0 }
    ' "$file"
}

# True if FILE contains a well-formed block for this $ORG (both markers present).
has_block() {
    local file="$1"
    [ -f "$file" ] || return 1
    grep -qxF "$(open_marker | tr -d '\n')" "$file" && \
        grep -qxF "$(close_marker | tr -d '\n')" "$file"
}

# Render the would-be block for the given content_file and compare against
# the current block in $file. Exit codes:
#   0  exact match (no change needed)
#   1  block missing (need to add)
#   2  block differs (need to replace)
block_state() {
    local file="$1"
    local content_file="$2"
    local would_be cur
    would_be=$(mktemp); build_block_file "$would_be" "$content_file"
    if ! has_block "$file"; then
        rm -f "$would_be"
        return 1
    fi
    cur=$(mktemp)
    extract_full_block "$file" > "$cur"
    if cmp -s "$would_be" "$cur"; then
        rm -f "$would_be" "$cur"
        return 0
    fi
    rm -f "$would_be" "$cur"
    return 2
}

# Pretty content stats: "<lines> line[s], <bytes> bytes"
content_stats() {
    local file="$1"
    local lines bytes
    lines=$(wc -l < "$file" 2>/dev/null | tr -d ' ')
    bytes=$(wc -c < "$file" 2>/dev/null | tr -d ' ')
    if [ "$lines" = "1" ]; then
        printf '%s line, %s bytes' "$lines" "$bytes"
    else
        printf '%s lines, %s bytes' "$lines" "$bytes"
    fi
}

# Render block body when this home file uses @-imports (Claude/Gemini/Cursor on
# the native-side pass). Use a ~/ path when possible — `@~/...` is portable
# across engineer machines and is honored by Claude, Gemini, and Cursor.
render_import_content() {
    local out="$1"
    printf '@%s\n' "$(pretty_path "$SOURCE_AGENTS")" > "$out"
}

# Render block body in cases where ~ expansion is unreliable (Codex inlines
# anyway, so this is currently used only for the Windows-host pass where the
# import path can't reach the WSL bok checkout — those passes inline instead).

# Render block body when this home file inlines content (Codex everywhere,
# AND every home file on the Windows-host pass).
render_inline_content() {
    local out="$1"
    cat "$SOURCE_AGENTS" > "$out"
}

# Atomic write of a string-content-from-file to the target file.
# Used by both install (replace/append) and uninstall (rewrite without block).
atomic_write() {
    local target="$1"
    local source="$2"
    local tmp="${target}.tmp.$$"
    mkdir -p "$(dirname "$target")"
    cp "$source" "$tmp"
    mv "$tmp" "$target"
}

# ---------------------------------------------------------------------------
# Per-file install / uninstall / dry-run actions
# ---------------------------------------------------------------------------

# Apply (install or dry-run) the block to a single file.
# Args: $1 = target file, $2 = content_file, [$3 = source label override]
apply_block() {
    local target="$1"
    local content_file="$2"
    local source_label="${3:-}"

    local pretty
    pretty=$(pretty_path "$target")

    local action state stats
    state=0
    block_state "$target" "$content_file" || state=$?

    stats=$(content_stats "$content_file")
    if [ -n "$source_label" ]; then
        stats="$(wc -c < "$content_file" | tr -d ' ') bytes inlined from $source_label"
    fi

    case "$state" in
        0)
            printf '%-50s = no change (block already current)\n' "$pretty"
            return
            ;;
        1)
            action="added"
            ;;
        2)
            action="replaced"
            ;;
    esac

    if [ "$DRY_RUN" = "1" ]; then
        case "$action" in
            added)    printf '%-50s + would add %s block (%s)\n'      "$pretty" "$ORG" "$stats" ;;
            replaced) printf '%-50s ~ would replace %s block (%s)\n'  "$pretty" "$ORG" "$stats" ;;
        esac
        return
    fi

    # Perform the write.
    mkdir -p "$(dirname "$target")"
    local new_full="${target}.new.$$"
    if [ ! -f "$target" ] || [ "$state" = "1" ]; then
        # Append-at-EOF path (covers both "no file" and "no block")
        if [ -f "$target" ]; then
            cat "$target" > "$new_full"
            # Ensure trailing newline before the block.
            if [ -s "$new_full" ] && [ -n "$(tail -c 1 "$new_full")" ]; then
                printf '\n' >> "$new_full"
            fi
        else
            : > "$new_full"
        fi
        {
            open_marker
            managed_line
            cat "$content_file"
            close_marker
        } >> "$new_full"
    else
        # In-place replace via awk.
        local block_tmp
        block_tmp=$(mktemp)
        {
            open_marker
            managed_line
            cat "$content_file"
            close_marker
        } > "$block_tmp"
        awk -v open_m="$(open_marker | tr -d '\n')" \
            -v close_m="$(close_marker | tr -d '\n')" \
            -v block_tmp="$block_tmp" '
            $0 == open_m {
                while ((getline line < block_tmp) > 0) print line
                close(block_tmp)
                in_block=1
                next
            }
            $0 == close_m && in_block { in_block=0; next }
            in_block { next }
            { print }
        ' "$target" > "$new_full"
        rm -f "$block_tmp"
    fi
    atomic_write "$target" "$new_full"
    rm -f "$new_full"

    case "$action" in
        added)    printf '%-50s + added %s block (%s)\n'    "$pretty" "$ORG" "$stats" ;;
        replaced) printf '%-50s ~ replaced %s block (%s)\n' "$pretty" "$ORG" "$stats" ;;
    esac
}

# Remove the block from a single file (or report what would be removed).
# Args: $1 = target file
remove_block_from() {
    local target="$1"
    local pretty
    pretty=$(pretty_path "$target")

    if [ ! -f "$target" ]; then
        return
    fi
    if ! has_block "$target"; then
        return
    fi

    local body
    body=$(mktemp)
    extract_block_body "$target" > "$body"
    local stats
    stats=$(content_stats "$body")
    rm -f "$body"

    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s - would remove %s block (%s)\n' "$pretty" "$ORG" "$stats"
        return
    fi

    local stripped="${target}.strip.$$"
    awk -v open_m="$(open_marker | tr -d '\n')" \
        -v close_m="$(close_marker | tr -d '\n')" '
        $0 == open_m { in_block=1; next }
        $0 == close_m && in_block { in_block=0; next }
        in_block { next }
        { print }
    ' "$target" > "$stripped"

    if ! grep -q '[^[:space:]]' "$stripped" 2>/dev/null; then
        rm -f "$stripped" "$target"
        printf '%-50s - removed %s block; file deleted (no other content)\n' "$pretty" "$ORG"
    else
        # Trim a single trailing blank line if we left one above the removed block.
        # (Cosmetic: keeps the file the same shape as before the block was added.)
        sed -e :a -e '/^$/{$d;N;ba' -e '}' "$stripped" > "${stripped}.trim" 2>/dev/null || cp "$stripped" "${stripped}.trim"
        mv "${stripped}.trim" "$stripped"
        atomic_write "$target" "$stripped"
        rm -f "$stripped"
        printf '%-50s - removed %s block (%s)\n' "$pretty" "$ORG" "$stats"
    fi
}

# ---------------------------------------------------------------------------
# Pass orchestration
# ---------------------------------------------------------------------------

# Iterate all home files for one pass, applying or removing the block.
# Args: $1 = "apply" or "remove"
#       $2 = home directory base (HOME on native, WIN_HOME on Windows pass)
#       $3 = "inline" or "import" (mode for Claude/Gemini/Cursor; Codex is always inline)
run_pass() {
    local action="$1"
    local home_base="$2"
    local mode="$3"

    # Files that vary by mode (import vs inline)
    local claude_file="$home_base/.claude/CLAUDE.md"
    local gemini_file="$home_base/.gemini/GEMINI.md"
    local cursor_file="$home_base/AGENTS.md"

    # Files that are always inlined (Codex, Xcode Codex).
    local codex_file="$home_base/.codex/AGENTS.md"
    local xcode_claude_file="$home_base/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig/CLAUDE.md"
    local xcode_codex_file="$home_base/Library/Developer/Xcode/CodingAssistant/codex/AGENTS.md"

    # Native-pass overrides (the Makefile sets these for the canonical pass; we
    # honor them only when the home_base IS the native $HOME).
    if [ "$home_base" = "$HOME" ]; then
        claude_file="$CLAUDE_HOME/CLAUDE.md"
        gemini_file="$GEMINI_HOME/GEMINI.md"
        cursor_file="$CURSOR_GLOBAL_FILE"
        codex_file="$CODEX_HOME/AGENTS.md"
        xcode_claude_file="$XCODE_CLAUDE_DIR/CLAUDE.md"
        xcode_codex_file="$XCODE_CODEX_DIR/AGENTS.md"
    fi

    local has_xcode=0
    [ -d "$home_base/Library/Developer/Xcode/CodingAssistant" ] && has_xcode=1

    if [ "$action" = "remove" ]; then
        remove_block_from "$claude_file"
        remove_block_from "$gemini_file"
        remove_block_from "$cursor_file"
        remove_block_from "$codex_file"
        if [ "$has_xcode" = "1" ]; then
            remove_block_from "$xcode_claude_file"
            remove_block_from "$xcode_codex_file"
        fi
        return
    fi

    # action = apply (or dry-run, controlled by DRY_RUN flag)

    local import_content inline_content
    import_content=$(mktemp); render_import_content "$import_content"
    inline_content=$(mktemp); render_inline_content "$inline_content"
    local source_label
    source_label="$(pretty_path "$SOURCE_AGENTS")"

    if [ "$mode" = "inline" ]; then
        # All home files inlined (Windows-host pass).
        apply_block "$claude_file" "$inline_content" "$source_label"
        apply_block "$gemini_file" "$inline_content" "$source_label"
        apply_block "$cursor_file" "$inline_content" "$source_label"
    else
        # @-imports for Claude/Gemini/Cursor (native pass).
        apply_block "$claude_file" "$import_content"
        apply_block "$gemini_file" "$import_content"
        apply_block "$cursor_file" "$import_content"
    fi

    # Codex never supports @-imports; always inline.
    apply_block "$codex_file" "$inline_content" "$source_label"

    if [ "$has_xcode" = "1" ]; then
        # Xcode Claude can use @-imports (Claude-like), Xcode Codex must inline.
        if [ "$mode" = "inline" ]; then
            apply_block "$xcode_claude_file" "$inline_content" "$source_label"
        else
            apply_block "$xcode_claude_file" "$import_content"
        fi
        apply_block "$xcode_codex_file" "$inline_content" "$source_label"
    fi

    rm -f "$import_content" "$inline_content"
}

# ---------------------------------------------------------------------------
# Legacy v1 cleanup
# ---------------------------------------------------------------------------

find_repos() {
    local root="$1"
    [ -n "$root" ] || return 0
    [ -d "$root" ] || return 0
    local real
    real=$(cd "$root" && pwd -P)
    find "$real" \
        \( -name node_modules -o -name .build -o -name Pods -o -name __pycache__ \
           -o -name .tox -o -name .venv -o -name venv -o -name .gradle \
           -o -name DerivedData -o -name .cache \) -prune \
        -o -name .git \( -type d -o -type f \) -print 2>/dev/null
}

# Remove a single .gitignore line (exact, full-line match). If the file becomes
# empty, delete it. Idempotent: a no-op when the line is absent.
remove_gitignore_line() {
    local gitignore="$1"
    local line="$2"
    [ -f "$gitignore" ] && [ -n "$line" ] || return 0
    grep -qxF "$line" "$gitignore" 2>/dev/null || return 0

    local pretty
    pretty=$(pretty_path "$gitignore")

    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s ~ would remove v1 entry: %s\n' "$pretty" "$line"
        return
    fi

    local tmp="${gitignore}.tmp.$$"
    grep -vxF "$line" "$gitignore" > "$tmp" || true
    if [ ! -s "$tmp" ]; then
        rm -f "$tmp" "$gitignore"
        printf '%-50s - removed v1 entry: %s; .gitignore deleted (empty)\n' "$pretty" "$line"
    else
        mv "$tmp" "$gitignore"
        printf '%-50s ~ removed v1 entry: %s\n' "$pretty" "$line"
    fi
}

# Delete a v1 per-project file (symlink or regular). Idempotent.
remove_legacy_file() {
    local f="$1"
    [ -e "$f" ] || [ -L "$f" ] || return 0
    local pretty
    pretty=$(pretty_path "$f")
    if [ "$DRY_RUN" = "1" ]; then
        printf '%-50s - would remove v1 file\n' "$pretty"
        return
    fi
    rm -f "$f"
    printf '%-50s - removed v1 file\n' "$pretty"
}

# Sweep one repo for v1 symlinks (per-pattern) and known gitignore entries.
sweep_repo_legacy() {
    local repo="$1"
    local cursor_rules="$repo/.cursor/rules"
    local jb_rules="$repo/.aiassistant/rules"
    local gitignore="$repo/.gitignore"

    if [ -n "$LEGACY_CURSOR_GLOB" ] && [ -d "$cursor_rules" ]; then
        local f
        while IFS= read -r f; do
            [ -n "$f" ] && remove_legacy_file "$f"
        done < <(find "$cursor_rules" -maxdepth 1 -name "$LEGACY_CURSOR_GLOB" 2>/dev/null || true)
    fi
    if [ -n "$LEGACY_JETBRAINS_GLOB" ] && [ -d "$jb_rules" ]; then
        local f
        while IFS= read -r f; do
            [ -n "$f" ] && remove_legacy_file "$f"
        done < <(find "$jb_rules" -maxdepth 1 -name "$LEGACY_JETBRAINS_GLOB" 2>/dev/null || true)
    fi

    [ -n "$LEGACY_GITIGNORE_CURSOR" ] && remove_gitignore_line "$gitignore" "$LEGACY_GITIGNORE_CURSOR"
    [ -n "$LEGACY_GITIGNORE_JETBRAINS" ] && remove_gitignore_line "$gitignore" "$LEGACY_GITIGNORE_JETBRAINS"
    return 0
}

run_legacy_cleanup() {
    [ -n "$PROJECTS_DIR" ] || return 0
    [ -d "$PROJECTS_DIR" ] || return 0

    local gitdir repo
    while IFS= read -r gitdir; do
        [ -z "$gitdir" ] && continue
        repo="${gitdir%/.git}"
        sweep_repo_legacy "$repo"
    done < <(find_repos "$PROJECTS_DIR")
}

print_conflicts() {
    if [ "${#CONFLICTS[@]}" -gt 0 ]; then
        printf '\n'
        printf 'CONFLICTS - manual intervention required (%d):\n' "${#CONFLICTS[@]}"
        local c
        for c in "${CONFLICTS[@]}"; do
            printf '  %s\n' "$c"
        done
    fi
}

# ---------------------------------------------------------------------------
# GitHub Copilot per-repo fan-out
# ---------------------------------------------------------------------------
# Copilot Cloud Agent runs on a GitHub-managed VM with $HOME set to a runner
# user, not yours, so there is no home-dir equivalent for these files. They
# must live committed in each repo. Two templates are repo-agnostic; the BOK
# is the single source of truth (see standards/ticket-to-pr-setup.md §5/§6).
#
# Install semantics (per user choice): write only when the file is missing
# or its content differs from source. No work, no working-tree noise on a
# clean re-run. When the BOK template changes, the next install propagates
# the new content (engineer reviews the diff in their working tree and
# commits per repo).
#
# Uninstall semantics: rm both files from every sibling repo's working tree.
# Each repo ends up with staged deletes the engineer commits at their pace.
#
# The bok itself is skipped: its own .github/ copies are deliberately
# divergent (the bok IS the BOK; it doesn't clone itself).

# Returns one of: "added", "updated", "unchanged".
copilot_file_action() {
    local target="$1"
    local source="$2"
    if [ ! -f "$target" ]; then
        echo added
    elif cmp -s "$target" "$source"; then
        echo unchanged
    else
        echo updated
    fi
}

# Install or dry-run the Copilot files for every repo under $PROJECTS_DIR.
# Skips the bok itself and any nested-under-another-repo paths.
apply_copilot() {
    [ -n "$COPILOT_SRC" ] || return 0
    [ -n "$PROJECTS_DIR" ] || return 0
    [ -d "$PROJECTS_DIR" ] || return 0

    local instr_src="$COPILOT_SRC/copilot-instructions.md"
    local steps_src="$COPILOT_SRC/copilot-setup-steps.yml"
    if [ ! -f "$instr_src" ] || [ ! -f "$steps_src" ]; then
        printf 'copilot: source templates missing under %s; skipping fan-out\n' \
            "$(pretty_path "$COPILOT_SRC")"
        return 0
    fi

    local projects_real
    projects_real=$(cd "$PROJECTS_DIR" && pwd -P)
    local repo_root_real=""
    [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT" ] && repo_root_real=$(cd "$REPO_ROOT" && pwd -P)

    local total=0 added=0 updated=0 unchanged=0 skipped_self=0 skipped_nested=0
    local gitdir repo

    while IFS= read -r gitdir; do
        [ -z "$gitdir" ] && continue
        repo="${gitdir%/.git}"

        if [ -n "$repo_root_real" ] && [ "$repo" = "$repo_root_real" ]; then
            skipped_self=$((skipped_self + 1))
            continue
        fi

        local nested=0 parent="$repo"
        while parent=$(dirname "$parent"); do
            case "$parent" in
                "$projects_real"|/) break ;;
            esac
            if [ -e "$parent/.git" ]; then nested=1; break; fi
        done
        if [ "$nested" = "1" ]; then
            skipped_nested=$((skipped_nested + 1))
            continue
        fi

        total=$((total + 1))

        local instr_target="$repo/.github/copilot-instructions.md"
        local steps_target="$repo/.github/workflows/copilot-setup-steps.yml"
        local a1 a2 verdict
        a1=$(copilot_file_action "$instr_target" "$instr_src")
        a2=$(copilot_file_action "$steps_target" "$steps_src")

        if [ "$a1" = "unchanged" ] && [ "$a2" = "unchanged" ]; then
            verdict=unchanged
        elif [ "$a1" = "added" ] || [ "$a2" = "added" ]; then
            verdict=added
        else
            verdict=updated
        fi

        case "$verdict" in
            unchanged)
                unchanged=$((unchanged + 1))
                ;;
            added)
                added=$((added + 1))
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s + would add copilot files (instructions=%s, setup-steps=%s)\n' \
                        "$(pretty_path "$repo")" "$a1" "$a2"
                else
                    mkdir -p "$repo/.github/workflows"
                    cp -f "$instr_src" "$instr_target"
                    cp -f "$steps_src" "$steps_target"
                    printf '%-50s + added copilot files\n' "$(pretty_path "$repo")"
                fi
                ;;
            updated)
                updated=$((updated + 1))
                if [ "$DRY_RUN" = "1" ]; then
                    printf '%-50s ~ would update copilot files (instructions=%s, setup-steps=%s)\n' \
                        "$(pretty_path "$repo")" "$a1" "$a2"
                else
                    mkdir -p "$repo/.github/workflows"
                    [ "$a1" != "unchanged" ] && cp -f "$instr_src" "$instr_target"
                    [ "$a2" != "unchanged" ] && cp -f "$steps_src" "$steps_target"
                    printf '%-50s ~ updated copilot files (BOK template propagated)\n' \
                        "$(pretty_path "$repo")"
                fi
                ;;
        esac
    done < <(find_repos "$PROJECTS_DIR")

    printf '\ncopilot: %d eligible repo(s) under %s\n' "$total" "$(pretty_path "$PROJECTS_DIR")"
    if [ "$DRY_RUN" = "1" ]; then
        printf '  + %d would be added (missing files)\n'           "$added"
        printf '  ~ %d would be updated (BOK template differs)\n'  "$updated"
        printf '  = %d unchanged\n'                                "$unchanged"
    else
        printf '  + %d added\n'      "$added"
        printf '  ~ %d updated\n'    "$updated"
        printf '  = %d unchanged\n'  "$unchanged"
    fi
    [ "$skipped_self" -gt 0 ]   && printf '  - %d skipped (this is the bok)\n'      "$skipped_self"
    [ "$skipped_nested" -gt 0 ] && printf '  - %d skipped (nested repo)\n'           "$skipped_nested"
    return 0
}

# Remove the Copilot files from every sibling repo. Skips the bok itself
# and nested repos for the same reasons as apply_copilot.
remove_copilot() {
    [ -n "$PROJECTS_DIR" ] || return 0
    [ -d "$PROJECTS_DIR" ] || return 0

    local projects_real
    projects_real=$(cd "$PROJECTS_DIR" && pwd -P)
    local repo_root_real=""
    [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT" ] && repo_root_real=$(cd "$REPO_ROOT" && pwd -P)

    local total=0 removed=0 absent=0 skipped_self=0 skipped_nested=0
    local gitdir repo

    while IFS= read -r gitdir; do
        [ -z "$gitdir" ] && continue
        repo="${gitdir%/.git}"

        if [ -n "$repo_root_real" ] && [ "$repo" = "$repo_root_real" ]; then
            skipped_self=$((skipped_self + 1))
            continue
        fi

        local nested=0 parent="$repo"
        while parent=$(dirname "$parent"); do
            case "$parent" in
                "$projects_real"|/) break ;;
            esac
            if [ -e "$parent/.git" ]; then nested=1; break; fi
        done
        if [ "$nested" = "1" ]; then
            skipped_nested=$((skipped_nested + 1))
            continue
        fi

        total=$((total + 1))

        local instr_target="$repo/.github/copilot-instructions.md"
        local steps_target="$repo/.github/workflows/copilot-setup-steps.yml"
        local had_any=0
        [ -f "$instr_target" ] && had_any=1
        [ -f "$steps_target" ] && had_any=1

        if [ "$had_any" = "0" ]; then
            absent=$((absent + 1))
            continue
        fi

        removed=$((removed + 1))
        if [ "$DRY_RUN" = "1" ]; then
            printf '%-50s - would remove copilot files\n' "$(pretty_path "$repo")"
        else
            rm -f "$instr_target" "$steps_target"
            printf '%-50s - removed copilot files\n' "$(pretty_path "$repo")"
        fi
    done < <(find_repos "$PROJECTS_DIR")

    printf '\ncopilot: %d eligible repo(s) under %s\n' "$total" "$(pretty_path "$PROJECTS_DIR")"
    if [ "$DRY_RUN" = "1" ]; then
        printf '  - %d would have copilot files removed\n' "$removed"
    else
        printf '  - %d had copilot files removed\n' "$removed"
    fi
    printf '  = %d already absent\n' "$absent"
    [ "$skipped_self" -gt 0 ]   && printf '  - %d skipped (this is the bok)\n' "$skipped_self"
    [ "$skipped_nested" -gt 0 ] && printf '  - %d skipped (nested repo)\n'      "$skipped_nested"
    return 0
}

# Read-only status for the Copilot fan-out (used by cmd_status).
status_copilot() {
    [ -n "$COPILOT_SRC" ] || return 0
    [ -n "$PROJECTS_DIR" ] || return 0
    [ -d "$PROJECTS_DIR" ] || return 0

    local instr_src="$COPILOT_SRC/copilot-instructions.md"
    local steps_src="$COPILOT_SRC/copilot-setup-steps.yml"
    if [ ! -f "$instr_src" ] || [ ! -f "$steps_src" ]; then
        printf 'copilot: source templates missing under %s\n' \
            "$(pretty_path "$COPILOT_SRC")"
        return
    fi

    local projects_real
    projects_real=$(cd "$PROJECTS_DIR" && pwd -P)
    local repo_root_real=""
    [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT" ] && repo_root_real=$(cd "$REPO_ROOT" && pwd -P)

    local total=0 current=0 stale=0 missing=0 partial=0
    local gitdir repo

    while IFS= read -r gitdir; do
        [ -z "$gitdir" ] && continue
        repo="${gitdir%/.git}"
        [ -n "$repo_root_real" ] && [ "$repo" = "$repo_root_real" ] && continue

        local nested=0 parent="$repo"
        while parent=$(dirname "$parent"); do
            case "$parent" in
                "$projects_real"|/) break ;;
            esac
            if [ -e "$parent/.git" ]; then nested=1; break; fi
        done
        [ "$nested" = "1" ] && continue

        total=$((total + 1))

        local a1 a2
        a1=$(copilot_file_action "$repo/.github/copilot-instructions.md" "$instr_src")
        a2=$(copilot_file_action "$repo/.github/workflows/copilot-setup-steps.yml" "$steps_src")

        if [ "$a1" = "unchanged" ] && [ "$a2" = "unchanged" ]; then
            current=$((current + 1))
        elif [ "$a1" = "added" ] && [ "$a2" = "added" ]; then
            missing=$((missing + 1))
        elif [ "$a1" = "added" ] || [ "$a2" = "added" ]; then
            partial=$((partial + 1))
        else
            stale=$((stale + 1))
        fi
    done < <(find_repos "$PROJECTS_DIR")

    printf '\ncopilot fan-out: %d eligible repo(s) under %s\n' "$total" "$(pretty_path "$PROJECTS_DIR")"
    printf '  = %d current (both files match BOK source)\n' "$current"
    [ "$stale"   -gt 0 ] && printf '  ~ %d stale (BOK template has been updated; run `make install`)\n' "$stale"
    [ "$partial" -gt 0 ] && printf '  ! %d partial (one of the two files is missing; run `make install`)\n' "$partial"
    [ "$missing" -gt 0 ] && printf '  + %d missing both files (run `make install` to fan out)\n' "$missing"
    return 0
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

# Print a header line with $ORG identity and which paths we're managing.
print_header() {
    local verb="$1"
    printf '%s: org=%s, source=%s\n' "$verb" "$ORG" "$(pretty_path "$SOURCE_AGENTS")"
    if [ -n "$WIN_HOME" ]; then
        printf '       windows host home detected at %s (dual pass)\n' "$(pretty_path "$WIN_HOME")"
    fi
}

cmd_install() {
    DRY_RUN=0
    init_win_home
    print_header "install"
    run_legacy_cleanup
    run_pass apply "$HOME" import
    if [ -n "$WIN_HOME" ]; then
        run_pass apply "$WIN_HOME" inline
    fi
    apply_copilot
    print_conflicts
}

cmd_uninstall() {
    DRY_RUN=0
    init_win_home
    print_header "uninstall"
    run_legacy_cleanup
    run_pass remove "$HOME" import
    if [ -n "$WIN_HOME" ]; then
        run_pass remove "$WIN_HOME" inline
    fi
    remove_copilot
    print_conflicts
}

cmd_dry_run() {
    DRY_RUN=1
    init_win_home
    print_header "dry-run"
    run_legacy_cleanup
    run_pass apply "$HOME" import
    if [ -n "$WIN_HOME" ]; then
        run_pass apply "$WIN_HOME" inline
    fi
    apply_copilot
    print_conflicts
}

cmd_status() {
    DRY_RUN=1   # status never writes; reuses the no-op rendering path
    init_win_home
    print_header "status"

    # Read-only summary per home file.
    local pretty
    local files=(
        "$CLAUDE_HOME/CLAUDE.md"
        "$GEMINI_HOME/GEMINI.md"
        "$CURSOR_GLOBAL_FILE"
        "$CODEX_HOME/AGENTS.md"
    )
    [ -d "$XCODE_CLAUDE_DIR" ] || [ -d "$HOME/Library/Developer/Xcode/CodingAssistant" ] && \
        files+=("$XCODE_CLAUDE_DIR/CLAUDE.md" "$XCODE_CODEX_DIR/AGENTS.md")

    local f
    for f in "${files[@]}"; do
        pretty=$(pretty_path "$f")
        if [ ! -f "$f" ]; then
            printf '%-50s ! file missing\n' "$pretty"
        elif has_block "$f"; then
            local body
            body=$(mktemp); extract_block_body "$f" > "$body"
            printf '%-50s OK %s block present (%s)\n' "$pretty" "$ORG" "$(content_stats "$body")"
            rm -f "$body"
        else
            printf '%-50s -- no %s block\n' "$pretty" "$ORG"
        fi
    done

    if [ -n "$WIN_HOME" ] && [ -d "$WIN_HOME" ]; then
        printf '\nwindows host (%s):\n' "$(pretty_path "$WIN_HOME")"
        for sub in .claude/CLAUDE.md .gemini/GEMINI.md AGENTS.md .codex/AGENTS.md; do
            f="$WIN_HOME/$sub"
            pretty=$(pretty_path "$f")
            if [ ! -f "$f" ]; then
                printf '%-50s ! file missing\n' "$pretty"
            elif has_block "$f"; then
                local body
                body=$(mktemp); extract_block_body "$f" > "$body"
                printf '%-50s OK %s block present (%s)\n' "$pretty" "$ORG" "$(content_stats "$body")"
                rm -f "$body"
            else
                printf '%-50s -- no %s block\n' "$pretty" "$ORG"
            fi
        done
    fi

    # Legacy artifacts still present?
    if [ -n "$PROJECTS_DIR" ] && [ -d "$PROJECTS_DIR" ]; then
        local lingering=0
        local gitdir repo
        while IFS= read -r gitdir; do
            [ -z "$gitdir" ] && continue
            repo="${gitdir%/.git}"
            if [ -n "$LEGACY_CURSOR_GLOB" ] && [ -d "$repo/.cursor/rules" ]; then
                if find "$repo/.cursor/rules" -maxdepth 1 -name "$LEGACY_CURSOR_GLOB" 2>/dev/null | grep -q .; then
                    lingering=$((lingering + 1))
                    continue
                fi
            fi
            if [ -n "$LEGACY_JETBRAINS_GLOB" ] && [ -d "$repo/.aiassistant/rules" ]; then
                if find "$repo/.aiassistant/rules" -maxdepth 1 -name "$LEGACY_JETBRAINS_GLOB" 2>/dev/null | grep -q .; then
                    lingering=$((lingering + 1))
                    continue
                fi
            fi
            if [ -n "$LEGACY_GITIGNORE_CURSOR" ] && [ -f "$repo/.gitignore" ] && \
               grep -qxF "$LEGACY_GITIGNORE_CURSOR" "$repo/.gitignore" 2>/dev/null; then
                lingering=$((lingering + 1))
                continue
            fi
            if [ -n "$LEGACY_GITIGNORE_JETBRAINS" ] && [ -f "$repo/.gitignore" ] && \
               grep -qxF "$LEGACY_GITIGNORE_JETBRAINS" "$repo/.gitignore" 2>/dev/null; then
                lingering=$((lingering + 1))
                continue
            fi
        done < <(find_repos "$PROJECTS_DIR")
        if [ "$lingering" -gt 0 ]; then
            printf '\n%d repo(s) under %s still have v1 artifacts; run `make install` or `make uninstall` to clean them.\n' \
                "$lingering" "$(pretty_path "$PROJECTS_DIR")"
        fi
    fi

    status_copilot
    print_conflicts
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
usage: $0 {install|uninstall|dry-run|status}

This script is invoked by the agents Makefile with the appropriate environment.
Run \`make help\` from the Makefile directory for user-facing entry points.
EOF
}

case "${1:-}" in
    install)    MODE=install;    cmd_install ;;
    uninstall)  MODE=uninstall;  cmd_uninstall ;;
    dry-run)    MODE=dry-run;    cmd_dry_run ;;
    status)     MODE=status;     cmd_status ;;
    -h|--help|help|"") usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
