"""What worker_guard.py and reviewer_guard.py share: where a command word may start in a Bash call, and which strings a
shell would run that a plain pass over the text masks.

Neither guard parses bash. Both are deny lists over regular expressions, so this module keeps each pattern
unambiguous (two ways to read one flag would make the match time exponential, and a hook that times out lets the call
through) and the guards set an alarm besides (see deadline()).

- START: a command word's position: the start, after a separator, a subshell or a substitution, past the shell's
  keywords and `{`, wrappers (sudo, env, command, exec, nohup, time, eval, timeout, nice, xargs) with their flags, and
  VAR=value assignments.
- bare(): the command with heredoc bodies and quoted strings set aside.
- inner_strings(): the strings a shell would run that bare() sets aside: the string after `sh|bash|zsh -c`, the
  arguments of an `eval`, every $(...) and backtick body (an unquoted heredoc body included), and a find's -exec
  actions.
- STDIN_SHELL: a shell that reads its commands from stdin, which nothing here can see.
"""

import re
import shlex
import signal

# Words that sit before the command word: wrappers that run what follows, and the shell's keywords and `{` that begin a
# command (`if make release; then ...`, `for d in a; do git push; done`, `{ git push; }`, `! git push`).
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
# The wrappers with flags of their own: the short flags that take a separate value, the long ones, and an operand
# pattern (timeout's duration). A boolean flag takes none, so `xargs -r echo git push` prints text; -l, -i, -e and their
# long forms take only an attached optional value. env -S runs a string, so it is denied outright (ENV_SPLIT).
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
# A shell's own flags: `-o NAME`, short clusters, long flags (and `--`). The three are disjoint, so a flag has one reading.
SHELL_FLAG = r"(?:-[Oo]\s+\S+|-(?!-)(?![Oo](?:\s|$))[A-Za-z]+|--[A-Za-z-]*)"


def _prefix_word(word):
    shorts, longs, operand = WRAPPER_FLAGS.get(word, ("", (), None))
    names = "|".join(sorted(longs))
    lookup = LOOKUP_FLAGS.get(word)
    alts = []
    if shorts:  # a cluster that ends in a value flag takes the next word (-s KILL, -rn 1); -n1 is one word
        alts.append(rf"-(?!-)[A-Za-z]*[{shorts}]\s+\S+")
    if longs:
        alts.append(rf"--(?:{names})\s+\S+")
    # The boolean flags are what the two forms above are not, so no flag is readable both ways.
    skip_value = rf"(?![A-Za-z]*[{shorts}](?:\s|$))" if shorts else ""
    skip_lookup = rf"(?![A-Za-z]*[{lookup}])" if lookup else ""
    alts.append(rf"-(?!-){skip_value}{skip_lookup}\S+")
    alts.append(rf"--(?!(?:{names})(?:\s|$))\S*" if longs else r"--\S*")
    if operand:
        alts.append(operand)
    path = r"(?:\S*/)?" if word in COMMAND_WORDS else ""
    return path + re.escape(word) + r"(?:\s+(?:" + "|".join(alts) + r"))*\s+"


# What may sit between a separator and the command word: prefix words with their flags, and VAR=value assignments.
PREFIX = (r"(?:" + "|".join(_prefix_word(w) for w in sorted(PREFIX_WORDS | set(WRAPPER_FLAGS), key=len, reverse=True))
          + r"|[A-Za-z_]\w*=\S*\s+)*")
LEAD = r"(?:^|[;&|(`\n]|\$\()\s*"
START = LEAD + PREFIX

ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$")
HEREDOC = re.compile(r"(?<!<)(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:(?P<body>.*?)\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a $'...' string is the single-quoted one after its $

SHELL_C = re.compile(START + SHELL_NAMES + r"(?:\s+" + SHELL_FLAG + r")*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?\s*\$?$")
# eval joins its arguments and runs them, so every argument counts, quoted or not.
EVAL_ARGS = re.compile(START + r"eval\s+((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|\n'\"])*)")
# `env -S 'git push'` runs the string; nothing here splits it as env does.
ENV_SPLIT = re.compile(START + r"env\b[^;&|\n]*?\s(?:-[A-Za-z]*S|--split-string)")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash < file`, `sh -`, `bash -s`), --version and
# --help aside.
STDIN_SHELL = re.compile(START + SHELL_NAMES + r"(?!\s+(?:--version|--help|-h)(?:\s|$))(?:\s+" + SHELL_FLAG + r")*?"
                         r"(?:\s+-[A-Za-z]*s[A-Za-z]*(?=\s|$)|\s+-(?=\s|$)|\s*(?:$|[;&|)`\n<]))")
# find's actions run in a shell of their own: its arguments (quote- and escape-aware, an escaped newline included), only
# at a command position.
FIND_ARGS = re.compile(START + r"find\b((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\[\s\S]|[^;&|\n\\'\"])*)")
FIND_ACTION = re.compile(r"\s-(?:exec|execdir|ok|okdir)\s+([^\n]*?)(?:\s*\\;|\s+\+(?=\s|$))")
FIND_WRITES = re.compile(r"\s-(?:delete|fprint\w*|fls)\b")
ANSI_ESCAPE = re.compile(r"\$'[^']*\\")
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


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
    return bool(shorts) and re.fullmatch(rf"-[A-Za-z]*[{shorts}]", word) is not None


def split_prefix(words):
    """(the index of the command word, the VAR=value assignments before it) in a command's words, past the prefix words,
    their flags and their operands. A lookup (`command -v x`) runs nothing: the index is past the end."""
    env, wrapper, i = {}, None, 0
    while i < len(words):
        w = words[i]
        m = ASSIGN.match(w)
        base = name_of(w) if name_of(w) in COMMAND_WORDS else w
        if m:
            env[m.group(1)] = m.group(2)
        elif base in PREFIX_WORDS or base in WRAPPER_FLAGS:
            wrapper = base
        elif wrapper and w.startswith("-") and not w.startswith("--") and wrapper in LOOKUP_FLAGS and \
                re.fullmatch(rf"-[A-Za-z]*[{LOOKUP_FLAGS[wrapper]}][A-Za-z]*", w):
            return len(words), env
        elif wrapper and w.startswith("-"):
            i += 1 if not takes_value(wrapper, w) else 2
            continue
        elif wrapper and WRAPPER_FLAGS.get(wrapper, (0, 0, None))[2] and re.fullmatch(WRAPPER_FLAGS[wrapper][2], w):
            pass
        else:
            break
        i += 1
    return i, env


def substitutions(text, quotes=True):
    """The (body, offset) of each $(...) and `...` substitution the shell would run in text: outside single quotes (but
    inside double ones), with escapes honoured and parentheses balanced across nested quotes. In an unquoted heredoc
    body (quotes=False) a quote is just a character."""
    out, i, n, dq = [], 0, len(text), False
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif quotes and c == '"':
            dq, i = not dq, i + 1
        elif quotes and c == "'" and not dq:
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
    """(text, kind, before) for each string a shell would run that bare() sets aside. kind is "shell" (the string after
    `sh -c`: its own command line, so the assignments before it count), "eval", "substitution" (only an earlier export
    reaches it), "find" (an action) or "opaque" (an ANSI-C string, which only a shell can decode). before is the
    command's text ahead of it."""
    plain = HEREDOC.sub(r"\1\4", command)
    found = []
    for m in QUOTED.finditer(plain):
        if SHELL_C.search(plain[:m.start()]):
            text = m.group(0)[1:-1].replace('\\"', '"')
            opaque = plain[m.start() - 1:m.start()] == "$" and "\\" in text
            found.append(("", "opaque", "") if opaque else (text, "shell", plain[:m.start()]))
    for m in EVAL_ARGS.finditer(plain):
        if ANSI_ESCAPE.search(m.group(1)):
            found.append(("", "opaque", ""))
            continue
        try:
            words = shlex.split(m.group(1))
        except ValueError:
            words = [m.group(1).replace("'", "").replace('"', "")]
        if words[:1] == ["--"]:
            words = words[1:]
        found.append((" ".join(words), "eval", plain[:m.start(1)]))
    for m in FIND_ARGS.finditer(plain):
        found += [(a.group(1), "find", plain[:m.start(1)]) for a in FIND_ACTION.finditer(m.group(1))]
    for m in HEREDOC.finditer(command):
        if not m.group(2) and m.group("body"):  # an unquoted heredoc body expands; a quoted one is inert
            found += [(body, "substitution", command[:m.start()]) for body, _ in substitutions(m.group("body"), quotes=False)]
    found += [(body, "substitution", plain[:at]) for body, at in substitutions(plain)]
    return found


def find_writes(command):
    """The find actions that write whatever they run: -delete, -fprint and -fls."""
    return [m.group(0).strip() for f in FIND_ARGS.finditer(command) for m in FIND_WRITES.finditer(f.group(1))]


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
