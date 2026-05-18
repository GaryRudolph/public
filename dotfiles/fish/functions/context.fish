function context --description 'Show or reload the active project context'
    set -l sub $argv[1]
    if test -z "$sub"
        set sub current
    end

    switch $sub
        case current
            echo $__active_context

        case show
            set -l name $argv[2]
            if test -z "$name"
                set name $__active_context
            end
            if test "$name" = personal
                echo "context: personal — no markers, no loadenvs"
                return 0
            end
            echo "context: $name"
            set -l mvar __context_markers_$name
            if set -q $mvar
                echo "  markers:"
                for kv in $$mvar
                    echo "    $kv"
                end
            else
                echo "  markers: (none)"
            end
            set -l lvar __context_loadenvs_$name
            if set -q $lvar
                echo "  loadenv:"
                for n in $$lvar
                    echo "    $n"
                end
            else
                echo "  loadenv: (none)"
            end

        case reload
            __context_init_active
            echo "context: reloaded $__active_context"

        case list
            echo "registered: $__context_registered"

        case -h --help help
            echo "usage: context [current|show <name>|reload|list]"
            echo "  current        Print the active context (default)."
            echo "  show [name]    Show markers + loadenv list for a context."
            echo "  reload         Reapply the current context (after editing the registry)."
            echo "  list           List registered contexts."

        case '*'
            echo "context: unknown subcommand '$sub'" >&2
            echo "         try: context [current|show <name>|reload|list]" >&2
            return 2
    end
end
