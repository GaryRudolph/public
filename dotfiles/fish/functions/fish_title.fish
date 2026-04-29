function fish_title --description 'Window/tab title: command line while running, context when idle'
    if test -n "$argv"
        # While a command is running, show the command line itself.
        echo $argv
    else
        # At the prompt, mirror the prompt's context line plus history index.
        printf '%s [%s]' (_fish_prompt_context) (_fish_histnum)
    end
end
