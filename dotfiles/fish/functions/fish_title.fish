function fish_title --description 'Window/tab title: command line while running, context when idle'
    if test -n "$argv"
        # While a command is running, show the command line itself.
        echo $argv
    else
        # At the prompt, mirror the prompt's bottom line: user@host:pwd, then
        # the venv-style `(ctx)` tag (when non-personal), then the history
        # index. Keeps the title in lockstep with the prompt so tab/window
        # labels reflect which world this shell lives in.
        if test -n "$__active_context"; and test "$__active_context" != personal
            printf '%s (%s) [%s]' (_fish_prompt_context) $__active_context (_fish_histnum)
        else
            printf '%s [%s]' (_fish_prompt_context) (_fish_histnum)
        end
    end
end
