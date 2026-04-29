function fish_prompt --description 'Three-line prompt: spacer, [time user@host:pwd], [hist]'
    # --- Line 1: full-width underlined spacer (separates output from prompt) ---
    set -l w $COLUMNS
    test -z "$w"; and set w (command tput cols 2>/dev/null)
    test -z "$w"; and set w 80

    set_color --underline
    string repeat -n $w ' '
    set_color normal

    # --- Line 2: [HH:MM:SS user@host:pwd]  (mirrors zsh PS1) ------------------
    printf '[%s ' (date +%H:%M:%S)
    set_color blue
    printf '%s' $USER
    set_color yellow
    printf '@'
    set_color green
    printf '%s' (prompt_hostname)
    set_color normal
    printf ':%s]\n' (prompt_pwd)

    # --- Line 3: input line ---------------------------------------------------
    printf '[%s] ' (_fish_histnum)
end
