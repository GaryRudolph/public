# Session detection and SSH alias flag.

if set -q SSH_CLIENT; or set -q SSH_TTY
    set -gx SESSION_TYPE ssh
else
    set -gx SESSION_TYPE local
end

# `ssh` alias adds -X (Linux) / -Y (macOS) for X11 forwarding when invoked.
if test (uname) = Darwin
    set -gx SSH_TUNNEL Y
else
    set -gx SSH_TUNNEL X
end
