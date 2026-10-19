#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Bash: keep personal-plan-orchestrate's reviewers read-only.

The reviewer (<plugin>:plan-reviewer) needs Bash for
git diff, git log and the repo's tests, and their instructions forbid writes.
Phase 0 showed the instruction is the only thing that stops a write (their
tools allowlist can't narrow Bash), so this hook denies the commands that
change a repo or a file when the hook input's agent_type names a reviewer:
git subcommands that write (commit, push, add, reset, checkout, switch,
rebase, merge, ...), file writers (rm, mv, cp, touch, mkdir, tee, sed -i,
...), output redirection to a file, and gh. A write on a later line, or
inside $(...) or backticks, counts too.

It is a deny list, so this is defence in depth: the instructions stay. Every
other caller (the main session, the plan's workers, any other agent) gets no
output and exit 0 at once; worker_guard.py holds the workers. So does input
that isn't JSON: this hook sees every Bash call of every session, so unlike
orchestrate_gate.py it fails open (the hooks file has no exit-2 fallback for
it). A reviewer's Bash call with no command string is denied. Heredoc bodies
and quoted strings are set aside before the checks, so
`git log --format='%h -> %s'` passes.
"""

import json
import re
import sys

REVIEWER = re.compile(r"^[a-z][a-z0-9-]*:plan-reviewer$")

GIT_OPTS = r"(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"
GIT_WRITE = re.compile(
    r"\bgit\b" + GIT_OPTS + r"\s+"
    r"(commit|push|add|rm|mv|reset|checkout|switch|restore|rebase|merge|cherry-pick|revert|stash|tag|branch\s+-[dDmMcC]|"
    r"clean|apply|am|pull|fetch|worktree|update-ref|update-index|config|remote|gc|prune|notes|replace|filter-branch)\b")
WRITERS = re.compile(r"(?:^|[;&|(`\n]\s*|\$\(\s*|\bsudo\s+|\bxargs\s+)(rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch)\b")
SED_IN_PLACE = re.compile(r"\b(?:sed|perl)\b[^;&|\n]*\s-[a-zA-Z]*i")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*(?!&|/dev/null\b)\S|\b[0-9]>>?\s*(?!&|/dev/null\b)[^\s&]")

HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


def problem(command):
    """Why a reviewer may not run command, or None."""
    command = bare(command)
    for rx, what in ((GIT_WRITE, "a git command that writes"), (WRITERS, "a command that writes files or acts outward"),
                     (SED_IN_PLACE, "an in-place edit"), (REDIRECT, "output redirected to a file")):
        m = rx.search(command)
        if m:
            return f"{what} ({m.group(0).strip()[:40]!r})"
    return None


def main():
    try:
        inp = json.load(sys.stdin)
    except ValueError:
        return  # not ours to judge; orchestrate_gate.py guards the launch itself
    if not isinstance(inp, dict) or not REVIEWER.match(str(inp.get("agent_type") or "")):
        return
    command = (inp.get("tool_input") or {}).get("command")
    why = problem(command) if isinstance(command, str) else "a Bash call with no command string"
    if why:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": "personal-plan-orchestrate reviewer: read-only; "
                                                 f"{why} is not allowed. Review with git diff, git log, git status, reads, and "
                                                 "tests that write only ignored build output; read their output inline."}}))


if __name__ == "__main__":
    main()
