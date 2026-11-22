"""What worker_guard.py and reviewer_guard.py share: where a command word may start in a Bash call, and which strings a
shell would run that a plain pass over the text masks.

Neither guard parses bash. Both are deny lists over regular expressions that catch the obvious patterns, not every shell
form (a form nobody writes is left alone: each pattern added is more to get wrong). This module keeps each pattern
unambiguous (two ways to read one flag would make the match time exponential, and a hook that times out lets the call
through), and the guards set an alarm besides (see deadline()).

- START: a command word's position: the start, after a separator, a subshell or a substitution, past the shell's
  keywords and `{`, wrappers (sudo, env, command, exec, nohup, time, eval, timeout, nice, xargs) with their flags, and
  VAR=value assignments.
- bare(): the command with heredoc bodies and quoted strings set aside.
- inner_strings(): the strings a shell would run that bare() sets aside: the quoted argument of `sh|bash|zsh -c`, the
  arguments of an `eval`, each $(...) and backtick body, and a find's -exec actions.
- STDIN_SHELL: a shell that reads its commands from stdin, which nothing here can see.
"""

import re
import signal
from collections import namedtuple

# Words that sit before the command word: wrappers that run what follows, and the shell's keywords and `{` that begin a
# command (`if make release; then ...`, `for d in a; do git push; done`, `{ git push; }`, `! git push`).
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
# The wrappers with flags of their own: the short flags that take the next word as a value (only when the flag stands
# alone: `-n 5`, `-I X`; `-I{}` is one word), the long ones, and an operand pattern (timeout's duration). A boolean flag
# takes none, so `xargs -r echo git push` prints text.
WRAPPER_FLAGS = {
    "timeout": ("sk", {"signal", "kill-after"}, r"\d+(?:\.\d+)?[smhd]?"),
    "nice": ("n", {"adjustment"}, None),
    "xargs": ("aEIJLnPsdRS", {"arg-file", "delimiter", "max-args", "max-chars", "max-procs", "process-slot-var"}, None),
    "sudo": ("ugCUhpRrT", {"user", "group", "chdir", "host", "prompt", "role", "type", "chroot", "other-user", "close-from"}, None),
    "env": ("uC", {"unset", "chdir"}, None),
}
# `command -v rm` looks a name up and runs nothing: these flags end the prefix.
LOOKUP_FLAGS = {"command": "vV"}
# Commands that may be named by path (/usr/bin/timeout); the keywords may not.
COMMAND_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "timeout", "nice", "xargs", "eval"}
SHELL_NAMES = r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)"
# A shell's own flags: a cluster ending in o or O takes an option name (-o pipefail, -euo pipefail), other clusters, and
# long flags (and `--`). The three are disjoint, so a flag has one reading.
SHELL_FLAG = r"(?:-(?!-)[A-Za-z]*[Oo]\s+\S+|-(?!-)(?![A-Za-z]*[Oo](?:\s|$))[A-Za-z]+|--[A-Za-z-]*)"


def _prefix_word(word):
    shorts, longs, operand = WRAPPER_FLAGS.get(word, ("", (), None))
    names = "|".join(sorted(longs))
    lookup = LOOKUP_FLAGS.get(word)
    alts = []
    if shorts:
        alts.append(rf"-[{shorts}]\s+\S+")
    if longs:
        alts.append(rf"--(?:{names})\s+\S+")
    # The boolean flags are what the two forms above are not, so no flag is readable both ways.
    skip_value = rf"(?![{shorts}](?:\s|$))" if shorts else ""
    skip_lookup = rf"(?![{lookup}](?:\s|$))" if lookup else ""
    alts.append(rf"-(?!-){skip_value}{skip_lookup}\S+")
    alts.append(rf"--(?!(?:{names})(?:\s|$))\S*" if longs else r"--\S*")
    if operand:
        alts.append(operand)
    path = r"(?:\S*/)?" if word in COMMAND_WORDS else ""
    return path + re.escape(word) + r"(?:\s+(?:" + "|".join(alts) + r"))*\s+"


# What may sit between a separator and the command word: prefix words with their flags, and VAR=value assignments.
PREFIX = (r"(?:" + "|".join(_prefix_word(w) for w in sorted(PREFIX_WORDS | set(WRAPPER_FLAGS), key=len, reverse=True))
          + r"|[A-Za-z_]\w*=\S*\s+)*")
START = r"(?:^|[;&|(`\n]|\$\()\s*" + PREFIX

ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$")
SEPARATOR = re.compile(r"\|\||&&|[;|&()`\n]|\$\(")
HEREDOC = re.compile(r"(?<!<)(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:.*?\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")

# The quoted argument of `sh -c` (a $'...' string is read as the plain quoted one).
SHELL_C = re.compile(START + SHELL_NAMES + r"(?:\s+" + SHELL_FLAG + r")*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?\s+\$?(?P<arg>'[^']*'|\"(?:[^\"\\]|\\.)*\")")
# eval joins its arguments and runs them, so every argument counts, quoted or not.
EVAL_ARGS = re.compile(START + r"eval\s+((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|\n'\"])*)")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash < file`, `sh -`, `bash -s`), --version and
# --help aside.
STDIN_SHELL = re.compile(START + SHELL_NAMES + r"(?!\s+(?:--version|--help|-h)(?:\s|$))(?:\s+" + SHELL_FLAG + r")*?"
                         r"(?:\s+-[A-Za-z]*s[A-Za-z]*(?=\s|$)|\s+-(?=\s|$)|\s*(?:$|[;&|)`\n<]))")
# find's actions run in a shell of their own: its arguments (quote- and escape-aware), at a command position.
FIND_ARGS = re.compile(START + r"(?:\S*/)?find\b((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\[\s\S]|[^;&|\n\\'\"])*)")
FIND_ACTION = re.compile(r"\s-(?:exec|execdir|ok|okdir)\s+([^\n]*?)(?:\s*\\;|\s+\+(?=\s|$))")
FIND_WRITES = re.compile(r"\s-(?:delete|fprint\w*|fls)\b")

Prefix = namedtuple("Prefix", "index env env_split")


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


def name_of(path):
    return path.rstrip("/").rsplit("/", 1)[-1]


def takes_value(wrapper, word):
    """Whether the flag word, in a wrapper's arguments, takes the next word as its value."""
    shorts, longs, _ = WRAPPER_FLAGS.get(wrapper, ("", (), None))
    if word.startswith("--"):
        return word[2:] in longs
    return len(word) == 2 and word[1] in shorts


def split_prefix(words):
    """A Prefix for a command's words, past the prefix words, their flags and their operands: index (of the command word;
    past the end for a lookup like `command -v x`, which runs nothing), env (the VAR=value assignments before it) and
    env_split (env -S, which runs a string nothing here splits)."""
    env, wrapper, i, split = {}, None, 0, False
    while i < len(words):
        w = words[i]
        m = ASSIGN.match(w)
        base = name_of(w) if name_of(w) in COMMAND_WORDS else w
        if m:
            env[m.group(1)] = m.group(2)
        elif base in PREFIX_WORDS or base in WRAPPER_FLAGS:
            wrapper = base
        elif wrapper in LOOKUP_FLAGS and len(w) == 2 and w[0] == "-" and w[1] in LOOKUP_FLAGS[wrapper]:
            return Prefix(len(words), env, split)
        elif wrapper and w.startswith("-"):
            split = split or (wrapper == "env" and (w == "-S" or w.startswith("--split-string")))
            i += 2 if takes_value(wrapper, w) else 1
            continue
        elif wrapper and WRAPPER_FLAGS.get(wrapper, (0, 0, None))[2] and re.fullmatch(WRAPPER_FLAGS[wrapper][2], w):
            pass
        else:
            break
        i += 1
    return Prefix(i, env, split)


def env_split(command):
    """Whether command runs `env -S`/`--split-string` (within env's own options)."""
    return any(split_prefix(segment.split()).env_split for segment in SEPARATOR.split(bare(command)))


def substitutions(text):
    """The (body, offset) of each $(...) and `...` substitution the shell would run in text: outside single quotes (but
    inside double ones), with escapes honoured and parentheses balanced across nested quotes."""
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
            out.append((text[i + 2:j - 1] if depth == 0 else text[i + 2:j], i))
            i = j
        elif c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append((text[i + 1:j], i))
            i = j + 1
        else:
            i += 1
    return out


def inner_strings(command):
    """(text, kind, before) for each string a shell would run that bare() sets aside. kind is "shell" (the argument of
    `sh -c`: its own command line, so the assignments before it count), "eval", "find" (an action) or "substitution"
    (only an earlier export reaches it). before is the command's text ahead of it."""
    plain = HEREDOC.sub(r"\1\4", command)
    found = []
    for m in SHELL_C.finditer(plain):
        arg = m.group("arg")
        found.append((arg[1:-1].replace('\\"', '"'), "shell", plain[:m.start("arg")]))
    for m in EVAL_ARGS.finditer(plain):
        found.append((m.group(1).replace("'", "").replace('"', ""), "eval", plain[:m.start(1)]))
    for m in FIND_ARGS.finditer(plain):
        found += [(a.group(1), "find", plain[:m.start(1)]) for a in FIND_ACTION.finditer(m.group(1))]
    found += [(body, "substitution", plain[:at]) for body, at in substitutions(plain)]
    return found


def find_writes(command):
    """The find actions that write whatever they run: -delete, -fprint and -fls."""
    plain = HEREDOC.sub(r"\1\4", command)
    return [m.group(0).strip() for f in FIND_ARGS.finditer(plain) for m in FIND_WRITES.finditer(f.group(1))]


class Timeout(BaseException):
    """Raised by the alarm: a command the guard could not analyse in time."""


def _alarm(signum, frame):
    raise Timeout()


def deadline(seconds=5):
    """Arm an alarm for the work after it (where the platform has SIGALRM), so a command that is slow to analyse is
    denied by the guard instead of timing the hook out, which lets the call through."""
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(seconds)
