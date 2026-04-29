function _fish_prompt_context --description 'user@host:pwd string used by fish_prompt and fish_title'
    printf '%s@%s:%s' $USER (prompt_hostname) (prompt_pwd)
end
