# Multi-account launchers (per-profile).
# See: macos-launchers/README.md (at repo root, sibling of dotfiles/).
#
# Personal = default behavior of bare `cursor`, `code`, and `opencode`. Bare
# `claude` defaults to the lolay account instead (personal via claude-personal).
# Each profile gets one alias per app: cursor-<slug>, claude-<slug>, code-<slug>.
#
# cursor-<slug> / code-<slug> require the matching <App> <LABEL>.app, built by
# `cd macos-launchers && make install` (installs to ~/Applications).
#
# Bare `cursor` / `claude` / `code` / `opencode` (defined below the explicit aliases) are
# path-aware wrappers: they route to the agerpoint app/config when the first
# path argument or pwd is inside ~/Projects/agerpoint/, otherwise they fall
# through to the default (personal; lolay for claude). See dotfiles/fish/README.md.

# --- agerpoint (slug=agerpoint, LABEL=AP) ---

function cursor-agerpoint --description 'Launch Cursor (Agerpoint, via Cursor AP.app)'
    open -a "Cursor AP" $argv
end

function claude-agerpoint --description 'Claude Code CLI (Agerpoint account)'
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-agerpoint"
    command claude $argv
end

function code-agerpoint --description 'Launch VS Code (Agerpoint, via Visual Studio Code AP.app)'
    open -a "Visual Studio Code AP" $argv
end

# --- lolay (slug=lolay, LABEL=LO) — Claude only ---
# Claude Team account; the routed default for everything outside agerpoint.
# Desktop counterpart is Claude LO.app.

function claude-lolay --description 'Claude Code CLI (Lolay account)'
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-lolay"
    command claude $argv
end

# --- personal — explicit escape hatch (default ~/.claude, no longer routed) ---

function claude-personal --description 'Claude Code CLI (personal account, ~/.claude)'
    # env -u, not `set -e`: inside agerpoint the marker is a global, and
    # `set -e` would erase it for the whole shell.
    env -u CLAUDE_CONFIG_DIR claude $argv
end

# Launch OpenCode.app via macOS open(1). Never invoke Contents/MacOS/OpenCode
# directly — that attaches Electron to the terminal and can trigger EPIPE errors.
function _opencode_launch_desktop --description 'open -a OpenCode [paths...]'
    set -l profile $argv[1]
    set -e argv[1]
    if test "$profile" = agerpoint
        env OPENCODE_APPNAME=opencode-agerpoint open -a OpenCode -- $argv
    else
        open -a OpenCode -- $argv
    end
end

# --- Path-aware bare commands ------------------------------------------------
# Use _context_from_argv to derive the context from the first path-like arg
# (or pwd if no path arg). Agerpoint is the only context with its own paid
# Cursor/Claude account today, so the routing is just "agerpoint or default."

function cursor --description 'Cursor, routed to agerpoint app or personal default'
    switch (_context_from_argv $argv)
        case agerpoint
            open -a "Cursor AP" $argv
        case '*'
            command cursor $argv
    end
end

function code --description 'VS Code, routed to agerpoint app or personal default'
    switch (_context_from_argv $argv)
        case agerpoint
            open -a "Visual Studio Code AP" $argv
        case '*'
            command code $argv
    end
end

function claude --description 'Claude Code CLI, routed to agerpoint or lolay config'
    switch (_context_from_argv $argv)
        case agerpoint
            set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-agerpoint"
            command claude $argv
        case '*'
            # Personal/lolay/nowline/deskhound all use the lolay Claude Team
            # account. Set explicitly so a path arg outside agerpoint wins over
            # the agerpoint marker inherited from pwd. Personal ~/.claude is
            # still reachable via claude-personal.
            set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-lolay"
            command claude $argv
    end
end

function opencode --description 'OpenCode: path-aware profile; CLI if installed else desktop app'
    set -l ctx (_context_from_argv $argv)
    if command -vq opencode
        if test "$ctx" = agerpoint
            set -lx OPENCODE_APPNAME opencode-agerpoint
        end
        command opencode $argv
    else
        _opencode_launch_desktop $ctx $argv
    end
end
