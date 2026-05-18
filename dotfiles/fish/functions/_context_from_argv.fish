function _context_from_argv --description 'Derive context from the first path-like argv (or pwd)'
    # Skim argv for the first non-flag argument and treat it as a path. If
    # nothing path-like shows up, fall back to the current working directory.
    set -l target (pwd)
    for arg in $argv
        string match -q -- '-*' $arg; and continue
        if test -e $arg
            set target (realpath $arg 2>/dev/null; or echo $arg)
        else
            set target $arg
        end
        break
    end
    _context_from_path $target
end
