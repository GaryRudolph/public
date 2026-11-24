# Multi-account launchers (per-profile).
# See: macos-launchers/README.md (at repo root, sibling of dotfiles/).
#
# Personal = default behavior of bare `cursor`, `code`, and `opencode`. Bare
# `claude` defaults to the lolay account instead (personal via claude-personal).
# Each profile gets one alias per app: claude-<slug>, code-<slug>. Cursor has
# no per-profile wrappers; it's always the personal account.
#
# code-<slug> requires the matching Visual Studio Code <LABEL>.app, built by
# `cd macos-launchers && make install` (installs to ~/Applications).
#
# Bare `claude` / `code` / `opencode` (defined below the explicit aliases) are
# path-aware wrappers: they route to a profile's app/config when the first path
# argument or pwd is inside ~/Projects/agerpoint/ or ~/Projects/ussander/,
# otherwise they fall through to the default (personal; lolay for claude). See
# dotfiles/fish/README.md.
#
# Editor launches go through `env (_context_clean_env)` (conf.d/80-context.fish):
# `open` and the editor CLIs hand the shell's env to the app, so this shell's
# context markers would otherwise leak into it. The profile wrappers set the
# profile's own env (CLAUDE_CONFIG_DIR, extensions dir) themselves.

# --- agerpoint (slug=agerpoint, LABEL=AP) ---

function claude-agerpoint --description 'Claude Code CLI (Agerpoint account)'
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-agerpoint"
    command claude $argv
end

function code-agerpoint --description 'Launch VS Code (Agerpoint, via Visual Studio Code AP.app)'
    env (_context_clean_env) open -a "Visual Studio Code AP" $argv
end

# --- ussander (slug=ussander, LABEL=US) ---

function claude-ussander --description 'Claude Code CLI (US Sander account)'
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-ussander"
    command claude $argv
end

function code-ussander --description 'Launch VS Code (US Sander, via Visual Studio Code US.app)'
    env (_context_clean_env) open -a "Visual Studio Code US" $argv
end

# --- lolay (slug=lolay, LABEL=LO) — Claude only ---
# Claude Team account; the routed default for everything outside agerpoint
# and ussander.
# Desktop counterpart is Claude LO.app.

function claude-lolay --description 'Claude Code CLI (Lolay account)'
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-lolay"
    command claude $argv
end

# --- personal — explicit escape hatch (default ~/.claude, no longer routed) ---

function claude-personal --description 'Claude Code CLI (personal account, ~/.claude)'
    # env -u, not `set -e`: inside agerpoint or ussander the marker is a global, and
    # `set -e` would erase it for the whole shell.
    env -u CLAUDE_CONFIG_DIR claude $argv
end

# Launch OpenCode.app via macOS open(1). Never invoke Contents/MacOS/OpenCode
# directly — that attaches Electron to the terminal and can trigger EPIPE errors.
function _opencode_launch_desktop --description 'open -a OpenCode [paths...]'
    set -l profile $argv[1]
    set -e argv[1]
    if contains -- $profile agerpoint ussander
        env OPENCODE_APPNAME=opencode-$profile open -a OpenCode -- $argv
    else
        # Drop a profile marker inherited from this shell's pwd, so a path
        # outside the profile trees opens the default profile.
        env -u OPENCODE_APPNAME open -a OpenCode -- $argv
    end
end

# --- Path-aware bare commands ------------------------------------------------
# Use _context_from_argv to derive the context from the first path-like arg
# (or pwd if no path arg). Agerpoint and ussander have their own accounts;
# everything else takes the default.

# Cursor has no per-profile app: always the personal one, minus this shell's
# context markers.
function cursor --description 'Cursor (personal), without the shell context env'
    env (_context_clean_env) cursor $argv
end

function code --description 'VS Code, routed to agerpoint/ussander app or personal default'
    switch (_context_from_argv $argv)
        case agerpoint
            env (_context_clean_env) open -a "Visual Studio Code AP" $argv
        case ussander
            env (_context_clean_env) open -a "Visual Studio Code US" $argv
        case '*'
            env (_context_clean_env) code $argv
    end
end

# The routed Claude config dirs, for the agents installer (agents/Makefile,
# when local.mk doesn't set it) and the allowlist scout. The personal ~/.claude
# (claude-personal) is left out, so the installer doesn't manage it; the scout
# still checks a session's own dir. Keep it in step with the CLAUDE_CONFIG_DIR
# values here, in dotfiles/zshrc and in macos-launchers.
set -gx CLAUDE_CONFIG_DIRS "$HOME/.claude-lolay:$HOME/.claude-agerpoint:$HOME/.claude-ussander"

function claude --description 'Claude Code CLI, routed to agerpoint, ussander or lolay config'
    set -l ctx (_context_from_argv $argv)
    switch $ctx
        case agerpoint ussander
            set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-$ctx"
            command claude $argv
        case '*'
            # Personal/lolay/nowline/deskhound all use the lolay Claude Team
            # account. Set explicitly so a path arg outside agerpoint/ussander
            # wins over a marker inherited from pwd. Personal ~/.claude is
            # still reachable via claude-personal.
            set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-lolay"
            command claude $argv
    end
end

function opencode --description 'OpenCode: path-aware profile; CLI if installed else desktop app'
    set -l ctx (_context_from_argv $argv)
    if command -vq opencode
        if contains -- $ctx agerpoint ussander
            set -lx OPENCODE_APPNAME opencode-$ctx
            command opencode $argv
        else
            # As above: the default profile, whatever this shell's pwd set.
            env -u OPENCODE_APPNAME opencode $argv
        end
    else
        _opencode_launch_desktop $ctx $argv
    end
end
