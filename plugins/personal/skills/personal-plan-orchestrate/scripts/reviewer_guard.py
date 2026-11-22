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
import shlex
import sys

REVIEWER = re.compile(r"^[a-z][a-z0-9-]*:plan-reviewer$")

GIT_OPTS = r"(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"
GIT_WRITE = re.compile(
    r"\bgit\b" + GIT_OPTS + r"\s+"
    r"(commit|push|add|rm|mv|reset|checkout|switch|restore|rebase|merge|cherry-pick|revert|stash|tag|branch\s+-[dDmMcC]|"
    r"clean|apply|am|pull|fetch|worktree|update-ref|update-index|config|remote|gc|prune|notes|replace|filter-branch)\b")
# worker_guard.py builds the same START, so a command is found behind the same keywords and wrappers.
# Words that sit before the command word: wrappers that run what follows, and the shell's keywords and `{` that
# begin a command (`if make release; then ...`, `for d in a; do git push; done`, `{ git push; }`, `! git push`).
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
# The wrappers with flags of their own: the short flags that take a separate value, the long ones, and an operand
# pattern (timeout's duration). A boolean flag takes none, so `xargs -r echo git push` prints text. -l, -i, -e and
# their long forms take only an attached optional value.
WRAPPER_FLAGS = {
    "timeout": ("sk", {"signal", "kill-after"}, r"[+-]?\d+(?:\.\d+)?[smhd]?"),
    "nice": ("n", {"adjustment"}, None),
    "xargs": ("aEIJLnPsdRS", {"arg-file", "delimiter", "max-args", "max-chars", "max-procs", "process-slot-var"}, None),
    "sudo": ("ugCUhpRrT", {"user", "group", "chdir", "host", "prompt", "role", "type", "chroot", "other-user", "close-from"}, None),
    "env": ("uCS", {"unset", "chdir", "split-string"}, None),
}
# Commands that may be named by path (/usr/bin/timeout); the keywords may not.
COMMAND_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "timeout", "nice", "xargs", "eval"}


def _prefix_word(word):
    shorts, longs, operand = WRAPPER_FLAGS.get(word, ("", (), None))
    alts = ([rf"-[{shorts}]\s+\S+"] if shorts else []) + ([r"--(?:" + "|".join(sorted(longs)) + r")\s+\S+"] if longs else [])
    alts += [r"-\S+"] + ([operand] if operand else [])
    path = r"(?:\S*/)?" if word in COMMAND_WORDS else ""
    return path + re.escape(word) + r"(?:\s+(?:" + "|".join(alts) + r"))*\s+"


# What may sit between a separator and the command word: prefix words with their flags, and VAR=value assignments.
PREFIX = r"(?:" + "|".join(_prefix_word(w) for w in sorted(PREFIX_WORDS | set(WRAPPER_FLAGS), key=len, reverse=True)) + r"|[A-Za-z_]\w*=\S*\s+)*"
# A command word's position: the start, or after a separator, a subshell or a substitution, past the prefix.
START = r"(?:^|[;&|(`\n]|\$\()\s*" + PREFIX
WRITERS = re.compile(START + r"(?:\S*/)?(rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch)\b")
_WRITE_CMDS = r"(?:\S*/)?(?:rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch|sh|bash|zsh)\b"
# find's own actions: -delete and the -fprint family write, and so does an -exec of a writer behind any wrapper.
# FIND_ARGS runs on across an escaped `\;`, which ends only an action, and stops at a real separator.
FIND_ARGS = re.compile(r"\bfind\b((?:\\.|[^;&|\n\\])*)")
FIND_WRITE = re.compile(r"\s-(?:delete|fprint\w*|fls)\b|\s-(?:exec|execdir|ok|okdir)\s+" + PREFIX + _WRITE_CMDS)
SED_IN_PLACE = re.compile(r"\b(?:sed|perl)\b[^;&|\n]*\s-[a-zA-Z]*i")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*(?!&|/dev/null\b)\S|\b[0-9]>>?\s*(?!&|/dev/null\b)[^\s&]")

HEREDOC = re.compile(r"(?<!<)(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:(?P<body>.*?)\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a $'...' string is the single-quoted one after its $


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


SHELL_C = re.compile(START + r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+(?:-[Oo]\s+\S+|-[A-Za-z-]+|--))*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?\s*\$?$")
# eval joins its arguments and runs them, so every argument counts, quoted or not.
EVAL_ARGS = re.compile(START + r"eval\s+((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|\n'\"])*)")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash <<< '...'`, `sh -`, `bash -s`): nothing here
# can see them.
STDIN_SHELL = re.compile(START + r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+-[A-Za-z-]+)*?"
                         r"(?:\s+-[A-Za-z]*s[A-Za-z]*(?=\s|$)|\s+-(?=\s|$)|\s*(?:$|[;&|)`\n]|<<))")


def substitutions(text):
    """The bodies of the $(...) and `...` substitutions the shell would run in text: outside single quotes (but inside
    double ones), with escapes honoured and parentheses balanced across nested quotes."""
    out, i, n, dq = [], 0, len(text), False
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == '"':
            dq, i = not dq, i + 1
        elif c == "'" and not dq:
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j, quote = 1, i + 2, None
            while j < n and depth:
                d = text[j]
                if d == "\\":
                    j += 1
                elif quote:
                    quote = None if d == quote else quote
                elif d in "'\"":
                    quote = d
                elif d == "(":
                    depth += 1
                elif d == ")":
                    depth -= 1
                j += 1
            out.append(text[i + 2:j - 1] if depth == 0 else text[i + 2:j])
            i = j
        elif c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def inner_strings(command):
    """The (string, text before it) pairs a shell would run that bare() sets aside: the quoted string after
    `sh|bash|zsh -c`, the joined arguments of an `eval`, and every substitution, in double quotes or an unquoted
    heredoc body included. A quoted heredoc body is inert."""
    plain = HEREDOC.sub(r"\1\4", command)
    found = [(m.group(0)[1:-1].replace('\\"', '"'), plain[:m.start()]) for m in QUOTED.finditer(plain)
             if SHELL_C.search(plain[:m.start()])]
    for m in EVAL_ARGS.finditer(plain):
        try:
            joined = " ".join(shlex.split(m.group(1)))
        except ValueError:
            joined = m.group(1).replace("'", "").replace('"', "")
        found.append((joined, plain[:m.start()]))
    live = HEREDOC.sub(lambda m: m.group(1) + m.group(4) + ("" if m.group(2) else "\n" + (m.group("body") or "")), command)
    found += [(body, live) for body in substitutions(live)]
    return found


def problem(command, depth=0):
    """Why a reviewer may not run command, or None."""
    if depth < 3:
        for text, _ in inner_strings(command):
            why = problem(text, depth + 1)
            if why:
                return why
    command = bare(command)
    for m in FIND_ARGS.finditer(command):
        hit = FIND_WRITE.search(m.group(1))
        if hit:
            return f"a find that deletes or writes ({hit.group(0).strip()[:40]!r})"
    for rx, what in ((STDIN_SHELL, "a shell that reads its commands from stdin"), (GIT_WRITE, "a git command that writes"), (WRITERS, "a command that writes files or acts outward"),
                     (SED_IN_PLACE, "an in-place edit"),
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
