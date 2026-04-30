# Multi-account launchers (per-profile).
# See: macos-launchers/README.md (at repo root, sibling of dotfiles/).
#
# Personal = default behavior of bare `cursor`, `claude`, and `code`.
# Each profile gets one alias per app: cursor-<slug>, claude-<slug>, code-<slug>.
#
# cursor-<slug> / code-<slug> require the matching <App> <LABEL>.app, built by
# `cd macos-launchers && make install` (installs to ~/Applications).

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
