function _fish_histnum --description 'Best-effort approximation of zsh %! (history event number)'
    # Counts entries returned by the history builtin. Not bit-identical to zsh's
    # global event id; it's a stable monotonic-ish index for the prompt.
    count (builtin history)
end
