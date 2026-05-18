# Multi-account launchers (per-profile).
# See: macos-launchers/README.md (at repo root, sibling of dotfiles/).
#
# Personal = default behavior of bare `cursor`, `claude`, and `code`.
# Each profile gets one alias per app: cursor-<slug>, claude-<slug>, code-<slug>.
#
# cursor-<slug> / code-<slug> require the matching <App> <LABEL>.app, built by
# `cd macos-launchers && make install` (installs to ~/Applications).
#
# Bare `cursor` / `claude` / `code` (defined below the explicit aliases) are
# path-aware wrappers: they route to the agerpoint app/config when the first
# path argument or pwd is inside ~/Projects/agerpoint/, otherwise they fall
# through to the personal default. See dotfiles/fish/README.md.

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

function claude --description 'Claude Code CLI, routed to agerpoint config or personal default'
    switch (_context_from_argv $argv)
        case agerpoint
            set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-agerpoint"
            command claude $argv
        case '*'
            # Personal/lolay/nowline/deskhound — bare claude uses ~/.claude.
            # If CLAUDE_CONFIG_DIR is already set by the context switcher
            # (only happens inside agerpoint), the command inherits it.
            command claude $argv
    end
end
