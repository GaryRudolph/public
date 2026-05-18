function fish_prompt --description 'Three-line prompt: spacer, [time user@host:pwd], (ctx?) [hist]'
    # --- Line 1: full-width underlined spacer (separates output from prompt) ---
    set -l w $COLUMNS
    test -z "$w"; and set w (command tput cols 2>/dev/null)
    test -z "$w"; and set w 80

    set_color --underline
    string repeat -n $w ' '
    set_color normal

    # --- Line 2: [HH:MM:SS user@host:pwd]  (mirrors zsh PS1) -----------------
    printf '[%s ' (date +%H:%M:%S)
    set_color blue
    printf '%s' $USER
    set_color yellow
    printf '@'
    set_color green
    printf '%s' (prompt_hostname)
    set_color normal
    printf ':%s' (prompt_pwd)
    printf ']\n'

    # --- Line 3: input line --------------------------------------------------
    # Per-context indicator as a venv-style left prefix. Personal (and unset)
    # renders nothing so the default shell looks unchanged; other contexts get
    # a bright magenta `(ctx)` tag before the history index.
    if test -n "$__active_context"; and test "$__active_context" != personal
        set_color --bold magenta
        printf '(%s) ' $__active_context
        set_color normal
    end
    printf '[%s] ' (_fish_histnum)
end
