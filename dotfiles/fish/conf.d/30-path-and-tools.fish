# Tool roots and base PATH additions.
# fish_add_path -gP prepends and dedupes (no need for `typeset -U path`).

set -gx HOMEBREW_HOME /opt/homebrew
set -gx TOOLS_HOME $HOME/Applications

fish_add_path -gP /usr/local/bin
test -d $HOME/.local/bin; and fish_add_path -gP $HOME/.local/bin
test -d $HOME/bin; and fish_add_path -gP $HOME/bin
