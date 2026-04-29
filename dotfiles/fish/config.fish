# Fish entry point.
#
# Load order:
#   1. conf.d/*.fish               — public defaults, lexical order (auto-loaded by fish)
#   2. host/<hostname -s>.fish     — per-machine settings (this file sources it)
#   3. ~/.config/fish-private/config.fish — private repo entry, if symlinked
#
# Set up via:
#   ln -snf "$HOME/Projects/personal/public/dotfiles/fish"  "$HOME/.config/fish"
#   ln -snf "$HOME/Projects/personal/private/dotfiles/fish" "$HOME/.config/fish-private"  # optional

# --- Per-machine host file ----------------------------------------------------

set -l _host (command hostname -s 2>/dev/null)
test -z "$_host"; and set _host (command hostname | string split . | head -n1)

set -l _hostfile "$__fish_config_dir/host/$_host.fish"
test -f "$_hostfile"; and source "$_hostfile"

# --- Private layer ------------------------------------------------------------
# Sibling of this fish config dir, so it works under any XDG_CONFIG_HOME.
# Default install: ~/.config/fish-private  →  ../private/dotfiles/fish
#
# `path normalize` is lexical (it strips `..` without following the symlink),
# which matters because $__fish_config_dir is itself a symlink — naive
# resolution would chase it into the public repo and miss the sibling.

set -l _priv (path normalize "$__fish_config_dir/../fish-private/config.fish")
test -f "$_priv"; and source "$_priv"
