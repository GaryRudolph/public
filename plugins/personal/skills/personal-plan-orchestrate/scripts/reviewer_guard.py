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
# A command word's position: the start, or after a separator, a subshell or a substitution, past the shell's keywords
# and `{` (`if true; then rm x; fi`, `for f in a; do rm $f; done`), wrappers with their flags and operands
# (`timeout 5 rm x`, `xargs -I{} rm {}`) and VAR=value prefixes. worker_guard.py builds the same START.
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
WRAPPERS = {"timeout", "nice", "xargs"}
_WORDS = "|".join(re.escape(w) for w in sorted(PREFIX_WORDS | WRAPPERS, key=len, reverse=True))
_WRAP_ARG = r"(?:-[A-Za-z]\s+\S+|--[\w-]+\s+\S+|-\S+|[+-]?\d+(?:\.\d+)?[smhd]?|[{%@]\S*)"
START = r"(?:^|[;&|(`\n]|\$\()\s*(?:(?:\S*/)?(?:" + _WORDS + r")(?:\s+" + _WRAP_ARG + r")*\s+|[A-Za-z_]\w*=\S*\s+)*"
WRITERS = re.compile(START + r"(?:\S*/)?(rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch)\b")
_WRITE_CMDS = r"(?:\S*/)?(?:rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch|sh|bash|zsh|sed|perl|python3?)\b"
FIND_WRITE = re.compile(r"\bfind\b[^;&|\n]*\s-(?:delete|fprint\w*|fls|(?:exec|execdir|ok|okdir)\s+" + _WRITE_CMDS + ")")
SHELL_C = re.compile(START + r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+(?:-[Oo]\s+\S+|-[A-Za-z-]+|--))*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?\s*\$?$")
EVAL = re.compile(START + r"eval\s*\$?$")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash <<< '...'`): nothing here can see them.
STDIN_SHELL = re.compile(r"(?:^|[|;&(`\n]|\$\()\s*(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+-[A-Za-z]+)*\s*(?:$|[;&|)`\n]|<<)")
SED_IN_PLACE = re.compile(r"\b(?:sed|perl)\b[^;&|\n]*\s-[a-zA-Z]*i")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*(?!&|/dev/null\b)\S|\b[0-9]>>?\s*(?!&|/dev/null\b)[^\s&]")

HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:.*?\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a $'...' string is the single-quoted one after its $


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def inner_strings(command):
    """The strings a shell runs that bare() would set aside: the quoted string after `sh|bash|zsh -c` or `eval`, and
    the body of a $(...) or backtick substitution inside double quotes (the shell runs it)."""
    command = HEREDOC.sub(r"\1\4", command)
    found = []
    for m in QUOTED.finditer(command):
        text = m.group(0)[1:-1]
        if SHELL_C.search(command[:m.start()]) or EVAL.search(command[:m.start()]):
            found.append(text.replace('\\"', '"'))
        if m.group(0)[0] == '"':
            found += [x or y for x, y in SUBSTITUTION.findall(text)]
    return found


def problem(command, depth=0):
    """Why a reviewer may not run command, or None."""
    if depth < 3:
        for inner in inner_strings(command):
            why = problem(inner, depth + 1)
            if why:
                return why
    command = bare(command)
    for rx, what in ((STDIN_SHELL, "a shell that reads its commands from stdin"), (GIT_WRITE, "a git command that writes"), (WRITERS, "a command that writes files or acts outward"),
                     (FIND_WRITE, "a find that deletes or writes"), (SED_IN_PLACE, "an in-place edit"),
                     (REDIRECT, "output redirected to a file")):
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
