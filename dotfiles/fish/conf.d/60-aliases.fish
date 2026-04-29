# Aliases ported from zshrc.
#
# Functions are used (instead of `alias`) when the body shadows a builtin/binary,
# needs deferred argument expansion, or contains awkward quoting.

# --- Generic ------------------------------------------------------------------
alias mroe 'more'
alias whois 'whois -h whois'
alias h 'history'
alias md 'mkdir'
alias rd 'rmdir'
alias cls 'clear'
alias x 'exit'
alias copy 'cp'
alias move 'mv'
alias back 'cd -'

# Bypass any function shadowing of pwd (kept for parity with zshrc).
function pwd --description 'Always use /bin/pwd'
    command /bin/pwd $argv
end

# --- ls family (platform-aware) ----------------------------------------------
if test (uname) = Darwin
    function ls --wraps ls --description 'colored ls (Darwin)'
        command ls -FqG $argv
    end
    function dir --wraps ls --description 'long colored ls'
        command ls -laFG $argv
    end
    function l --wraps ls --description 'long colored ls'
        command ls -alFG $argv
    end
else
    function ls --wraps ls --description 'colored ls (Linux/BSD)'
        command ls -Fq --color $argv
    end
    function dir --wraps ls --description 'long colored ls'
        command ls -laF --color $argv
    end
    function l --wraps ls --description 'long colored ls'
        command ls -alF --color $argv
    end
end

# --- ssh with X11 tunnel flag (uses $SSH_TUNNEL from 10-session.fish) --------
function ssh --wraps ssh --description 'ssh with -X/-Y tunnel flag'
    command ssh -$SSH_TUNNEL $argv
end

# --- macOS-specific shortcuts ------------------------------------------------
alias entitlements 'codesign -dvvvv --entitlements -'
alias fixvpn 'sudo /System/Library/StartupItems/CiscoVPN/CiscoVPN restart'
alias enablelid 'sudo pmset -a lidwake 1'
alias disablelid 'sudo pmset -a lidwake 0'
alias ql 'qlmanage -p'
alias flushdns 'sudo discoveryutil mdnsflushcache; sudo discoveryutil udnsflushcaches'

# --- Git ---------------------------------------------------------------------
alias gitu 'git pull; and git submodule init; and git submodule update'

function gitkt --description 'git log graph (kt format)'
    git log --graph \
        --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' \
        --abbrev-commit --date=relative $argv
end

# --- Apple developer tools ---------------------------------------------------
alias symbolicate '/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/Library/PrivateFrameworks/DTDeviceKitBase.framework/Versions/Current/Resources/symbolicatecrash'
alias pdf_join '/System/Library/Automator/Combine PDF Pages.action/Contents/Resources/join.py'

# --- Misc --------------------------------------------------------------------
function filetree --description 'ASCII tree of current directory'
    ls -R | grep ':$' | sed -e 's/:$//' -e 's/[^-][^\/]*\//--/g' -e 's/^/ /' -e 's/-/|/'
end
