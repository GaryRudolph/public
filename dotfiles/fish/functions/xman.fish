function xman --description 'Open a man page in macOS Terminal/man viewer'
    open "x-man-page://"(string join / $argv)
end
