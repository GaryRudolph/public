# Placeholder for fish history tweaks.
#
# Fish defaults are reasonable: dedup on search, per-session merge on exit,
# trailing whitespace trimmed during history search.
#
# To implement a HISTORY_IGNORE-style scrub (drop x/exit/ls/h/history/pwd/cd/cd ..
# from the persisted history), uncomment and tune the handler below.

# function __scrub_history --on-event fish_postexec
#     set -l ignore '^(x|exit|ls|h|history|pwd|cd|cd \.\.)$'
#     if string match -rq -- $ignore $argv[1]
#         builtin history delete --exact --case-sensitive -- $argv[1] 2>/dev/null
#     end
# end
