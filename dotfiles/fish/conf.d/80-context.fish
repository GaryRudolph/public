# Per-context auto-switching: on cd, detect which project tree you're in
# (personal/lolay/agerpoint/nowline/deskhound), set the non-secret env markers
# for that context, and `loadenv` the registered private dotenv files. When you
# cd out, unset/unload everything the previous context applied.
#
# Public side (this file): the mechanism. No client names beyond the directory
# mapping below.
# Private side: `fish-private/conf.d/context-registry.fish` declares what
# markers and loadenv files each context wants. See dotfiles/fish/README.md.

# --- Directory → context mapping ----------------------------------------------
# Alternating pairs of (path-prefix, context-name). First match wins, anything
# unmatched is `personal`. Edit here to wire a new project tree.
set -g __context_path_map \
    "$HOME/Projects/agerpoint" agerpoint \
    "$HOME/Projects/nowline"   nowline \
    "$HOME/Projects/deskhound" deskhound \
    "$HOME/Projects/lolay"     lolay

# --- Registry (populated by private context-registry.fish) -------------------
# `context_register <name> --markers K=v ... --loadenv name1 name2`
# stores:
#   __context_markers_<name>  -- list of K=v strings
#   __context_loadenvs_<name> -- list of loadenv short names
# and appends <name> to __context_registered (informational; not iterated).
function context_register --description 'Declare markers + loadenv list for a context'
    set -l ctx $argv[1]
    if test -z "$ctx"
        echo "context_register: missing context name" >&2
        return 2
    end
    set -e argv[1]

    set -l markers
    set -l loadenvs
    set -l mode
    for arg in $argv
        switch $arg
            case '--markers'
                set mode markers
            case '--loadenv'
                set mode loadenvs
            case '*'
                switch $mode
                    case markers
                        set -a markers $arg
                    case loadenvs
                        set -a loadenvs $arg
                    case '*'
                        echo "context_register $ctx: stray arg '$arg' (expected --markers or --loadenv first)" >&2
                        return 2
                end
        end
    end

    set -g __context_markers_$ctx $markers
    set -g __context_loadenvs_$ctx $loadenvs
    if not contains $ctx $__context_registered
        set -g __context_registered $__context_registered $ctx
    end
end

# --- Path → context detector --------------------------------------------------
function _context_from_path --description 'Return context name (personal/...) for a filesystem path'
    set -l p $argv[1]
    test -z "$p"; and set p (pwd)
    # Best-effort absolute path. realpath fails for non-existent targets, in
    # which case we fall back to the raw input (so the smart wrappers can still
    # route by an arg like `~/Projects/nowline/new-repo`).
    set -l abs (realpath $p 2>/dev/null; or echo $p)

    set -l pairs $__context_path_map
    set -l n (count $pairs)
    for i in (seq 1 2 $n)
        set -l prefix $pairs[$i]
        set -l name $pairs[(math $i + 1)]
        if test "$abs" = "$prefix"; or string match -q "$prefix/*" -- "$abs"
            echo $name
            return 0
        end
    end
    echo personal
end

# --- Apply / unapply ----------------------------------------------------------
# `_context_apply <name>`   sets the markers and runs the loadenvs.
# `_context_unapply <name>` unsets the markers and runs `unloadenv` for each.
# `personal` is a no-op for both — it has no registration.
function _context_apply
    set -l ctx $argv[1]
    test "$ctx" = personal; and return 0

    set -l marker_var __context_markers_$ctx
    if set -q $marker_var
        for kv in $$marker_var
            set -l parts (string split -m1 '=' -- $kv)
            test (count $parts) -eq 2; or continue
            set -gx $parts[1] $parts[2]
        end
    end

    set -l loadenv_var __context_loadenvs_$ctx
    if set -q $loadenv_var
        for name in $$loadenv_var
            # Silent skip if the env file is missing — partial setups (e.g. a
            # context with a placeholder before its credentials exist) should
            # not break the shell on every cd. loadenv prints its own errors.
            functions -q loadenv; and loadenv $name >/dev/null 2>&1
        end
    end
end

function _context_unapply
    set -l ctx $argv[1]
    test "$ctx" = personal; and return 0

    set -l loadenv_var __context_loadenvs_$ctx
    if set -q $loadenv_var
        for name in $$loadenv_var
            functions -q unloadenv; and unloadenv $name >/dev/null 2>&1
        end
    end

    set -l marker_var __context_markers_$ctx
    if set -q $marker_var
        for kv in $$marker_var
            set -l key (string split -m1 '=' -- $kv)[1]
            set -e $key 2>/dev/null
        end
    end
end

# --- PWD handler --------------------------------------------------------------
function __context_on_pwd_changed --on-variable PWD
    set -l new (_context_from_path (pwd))
    set -l old $__active_context
    test "$new" = "$old"; and return 0

    test -n "$old"; and _context_unapply $old
    set -gx __active_context $new
    _context_apply $new
end

# --- Init / reapply -----------------------------------------------------------
# Called once after the private registry has been loaded so the shell's
# initial directory ends up with the right context. Also exposed for `context
# reload` so users can re-source after editing the registry.
function __context_init_active
    set -l new (_context_from_path (pwd))
    set -l old $__active_context
    if test "$new" != "$old"
        test -n "$old"; and _context_unapply $old
    else
        # Same context, but markers/loadenvs may have changed -- unapply first
        # so reload is idempotent.
        test -n "$old"; and _context_unapply $old
    end
    set -gx __active_context $new
    _context_apply $new
end
